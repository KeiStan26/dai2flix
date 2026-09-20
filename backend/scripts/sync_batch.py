"""Cron synchronization batch script for Daini-group VOD.

Responsibilities:
1. Multi-execution prevention via file lock (PID checking & stale lock handling).
2. Fetch playlists and video items using minimal quota (playlists.list, playlistItems.list, videos.list).
3. Upsert data to SQLite database with WAL mode.
4. Detect newly discovered videos and trigger Gemini LLM enrichment ONCE per video.
5. Provide resilient error logging and graceful failure modes.
"""

import argparse
import atexit
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

# Ensure backend root is on PYTHONPATH
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import AIEnrichment, Playlist, PlaylistVideo, Video
from app.services.enricher import MetadataEnricher
from app.services.youtube import YouTubeClient, YouTubeQuotaExceededError, derive_channel_playlist_id

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sync_batch")


class BatchLock:
    """Robust file-based lock with PID validation to prevent overlapping batch runs."""

    def __init__(self, lock_path: str, stale_seconds: int = 7200):
        self.lock_file = Path(lock_path).resolve()
        self.stale_seconds = stale_seconds
        self.acquired = False

    def acquire(self) -> bool:
        """Attempt to acquire exclusive lock. Returns True on success, False if already running."""
        try:
            if self.lock_file.exists():
                # Check if existing lock is stale or process is dead
                try:
                    content = self.lock_file.read_text().strip()
                    parts = content.split(":")
                    if len(parts) >= 2:
                        old_pid = int(parts[0])
                        old_timestamp = float(parts[1])
                        now = datetime.now(timezone.utc).timestamp()

                        # If older than stale_seconds, treat as stale
                        if (now - old_timestamp) < self.stale_seconds:
                            if self._is_process_running(old_pid):
                                logger.warning(
                                    "Another sync_batch process (PID %d) is already active. Exiting.",
                                    old_pid,
                                )
                                return False
                            else:
                                logger.info("Found dead lock file from PID %d. Overwriting.", old_pid)
                except Exception as e:
                    logger.warning("Error inspecting existing lock file: %s. Overwriting.", e)

            # Write current PID and timestamp
            now_ts = datetime.now(timezone.utc).timestamp()
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file.write_text(f"{os.getpid()}:{now_ts}")
            self.acquired = True
            atexit.register(self.release)
            return True

        except Exception as e:
            logger.error("Failed to acquire batch lock: %s", e)
            return False

    def release(self) -> None:
        """Release lock file upon process completion."""
        if self.acquired:
            try:
                if self.lock_file.exists():
                    self.lock_file.unlink(missing_ok=True)
                self.acquired = False
                logger.info("Batch lock released successfully.")
            except Exception as e:
                logger.warning("Failed to remove lock file %s: %s", self.lock_file, e)

    @staticmethod
    def _is_process_running(pid: int) -> bool:
        """Check if process with PID is currently alive on Windows or POSIX."""
        if pid <= 0:
            return False
        try:
            if os.name == "nt":
                # Windows process existence check
                import ctypes

                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if handle == 0:
                    return False
                kernel32.CloseHandle(handle)
                return True
            else:
                # POSIX process existence check
                os.kill(pid, 0)
                return True
        except (OSError, ProcessLookupError):
            return False


class SyncService:
    """Orchestrates YouTube data harvesting, SQLite updates, and Gemini enrichment."""

    def __init__(
        self,
        db: Session,
        youtube_client: Optional[YouTubeClient] = None,
        enricher: Optional[MetadataEnricher] = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.youtube_client = youtube_client
        self.enricher = enricher

    def run(self) -> Dict[str, int]:
        """Execute full differential sync pipeline."""
        stats = {
            "playlists_synced": 0,
            "videos_synced": 0,
            "videos_enriched": 0,
            "errors": 0,
        }

        if not self.youtube_client:
            logger.warning("YouTube client is not initialized (missing API key?). Skipping sync.")
            return stats

        try:
            all_video_ids: Set[str] = set()
            playlist_items_map: Dict[str, List[Dict]] = {}
            members_only_ids: Set[str] = set()

            # 1. Fetch UUMO (Members-only playlist) if channel_id is available
            channel_id = self.settings.channel_id
            uumo_id = derive_channel_playlist_id(channel_id, "UUMO")
            if uumo_id:
                try:
                    logger.info("Fetching members-only playlist (%s)...", uumo_id)
                    mo_items = self.youtube_client.get_playlist_items(uumo_id, max_results=200)
                    for item in mo_items:
                        members_only_ids.add(item["video_id"])
                        all_video_ids.add(item["video_id"])
                    logger.info("Identified %d members-only video IDs from UUMO playlist.", len(members_only_ids))
                    playlist_items_map[uumo_id] = mo_items

                    # Register/upsert this playlist entity
                    db_pl = self.db.query(Playlist).filter_by(id=uumo_id).first()
                    thumb = mo_items[0].get("thumbnail_url") if mo_items else None
                    if not db_pl:
                        db_pl = Playlist(
                            id=uumo_id,
                            title="👑 メンバーシップ限定アーカイブ",
                            description="だいにぐるーぷ公式チャンネル メンバーシップ限定コンテンツ",
                            thumbnail_url=thumb,
                            display_order=5,
                        )
                        self.db.add(db_pl)
                    else:
                        db_pl.title = "👑 メンバーシップ限定アーカイブ"
                        if thumb:
                            db_pl.thumbnail_url = thumb
                    self.db.commit()
                    stats["playlists_synced"] += 1
                except Exception as mo_err:
                    logger.warning("Could not fetch UUMO playlist (%s): %s. Will rely on keywords.", uumo_id, mo_err)

            # Helper for members-only detection
            def is_mo_video(vid: str, title: str, desc: str) -> bool:
                if vid in members_only_ids:
                    return True
                text = f"{title} {desc}".lower()
                keywords = ["メンバー限定", "メンバーシップ限定", "メン限", "【メンバーシップ】", "会員限定", "ファンクラブ限定", "fc限定"]
                return any(kw in text for kw in keywords)

            # 2. Resolve Target Playlists
            target_playlists = self._resolve_target_playlists()
            logger.info("Found %d target playlists for synchronization.", len(target_playlists))

            # 3. Sync Playlists and collect video IDs
            for p in target_playlists:
                try:
                    # Upsert playlist entity
                    db_playlist = self.db.query(Playlist).filter_by(id=p.id).first()
                    if not db_playlist:
                        db_playlist = Playlist(
                            id=p.id,
                            title=p.title,
                            description=p.description,
                            thumbnail_url=p.thumbnail_url,
                        )
                        self.db.add(db_playlist)
                    else:
                        db_playlist.title = p.title
                        db_playlist.description = p.description
                        db_playlist.thumbnail_url = p.thumbnail_url
                    self.db.commit()
                    stats["playlists_synced"] += 1

                    # Fetch playlist items
                    items = self.youtube_client.get_playlist_items(p.id)
                    playlist_items_map[p.id] = items
                    for item in items:
                        all_video_ids.add(item["video_id"])

                except Exception as e:
                    logger.error("Error syncing playlist %s: %s", p.id, e)
                    self.db.rollback()
                    stats["errors"] += 1

            # 4. Batch fetch detailed video metadata (50 IDs per API unit)
            if all_video_ids:
                logger.info("Fetching details for %d unique videos...", len(all_video_ids))
                details_map = self.youtube_client.get_videos_details(list(all_video_ids))

                # Upsert videos with is_members_only flag
                for vid, vdata in details_map.items():
                    is_mo = is_mo_video(vid, vdata.title, vdata.description or "")
                    db_video = self.db.query(Video).filter_by(id=vid).first()
                    if not db_video:
                        db_video = Video(
                            id=vdata.id,
                            title=vdata.title,
                            description=vdata.description,
                            published_at=vdata.published_at,
                            thumbnail_url=vdata.thumbnail_url,
                            duration_seconds=vdata.duration_seconds,
                            view_count=vdata.view_count,
                            is_members_only=is_mo,
                        )
                        self.db.add(db_video)
                    else:
                        db_video.title = vdata.title
                        db_video.description = vdata.description
                        db_video.published_at = vdata.published_at
                        db_video.thumbnail_url = vdata.thumbnail_url
                        db_video.duration_seconds = vdata.duration_seconds
                        db_video.view_count = vdata.view_count
                        db_video.is_members_only = is_mo
                self.db.commit()
                stats["videos_synced"] = len(details_map)

                # Update playlist-video associations
                for pid, items in playlist_items_map.items():
                    # Clear previous associations for this playlist to refresh ordering
                    self.db.query(PlaylistVideo).filter_by(playlist_id=pid).delete()
                    for item in items:
                        vid = item["video_id"]
                        if vid in details_map:
                            assoc = PlaylistVideo(
                                playlist_id=pid,
                                video_id=vid,
                                position=item["position"],
                            )
                            self.db.add(assoc)
                    self.db.commit()

            # 5. Backfill/update is_members_only status for existing videos in DB
            all_db_videos = self.db.query(Video).all()
            updated_mo_count = 0
            for v in all_db_videos:
                should_be_mo = is_mo_video(v.id, v.title, v.description or "")
                if v.is_members_only != should_be_mo:
                    v.is_members_only = should_be_mo
                    updated_mo_count += 1
            if updated_mo_count > 0:
                self.db.commit()
                logger.info("Backfilled is_members_only status for %d existing videos.", updated_mo_count)

            # 6. Trigger AI enrichment for videos that don't have it yet (NEW videos only)
            stats["videos_enriched"] = self._enrich_new_videos()

        except YouTubeQuotaExceededError as qe:
            logger.error("Sync aborted due to YouTube quota limits: %s", qe)
            self.db.rollback()
            stats["errors"] += 1
        except Exception as e:
            logger.error("Unhandled error during sync pipeline: %s", e, exc_info=True)
            self.db.rollback()
            stats["errors"] += 1

        return stats

    def _resolve_target_playlists(self):
        """Determine playlists to sync based on settings."""
        explicit_ids = self.settings.playlist_id_list
        if explicit_ids:
            # Sync explicit playlists
            playlists = []
            for pid in explicit_ids:
                try:
                    items = self.youtube_client.get_playlist_items(pid, max_results=1)
                    title = f"Playlist {pid}"
                    thumb = None
                    if items:
                        thumb = items[0].get("thumbnail_url")
                    from app.services.youtube import YouTubePlaylistData

                    playlists.append(
                        YouTubePlaylistData(
                            id=pid,
                            title=title,
                            description="",
                            thumbnail_url=thumb,
                        )
                    )
                except Exception as e:
                    logger.warning("Could not pre-fetch playlist %s: %s", pid, e)
            return playlists

        # Otherwise discover all channel playlists
        channel_id = self.settings.channel_id
        return self.youtube_client.get_channel_playlists(channel_id)

    def _enrich_new_videos(self) -> int:
        """Find videos lacking AI enrichment and generate Netflix-style metadata."""
        if not self.enricher:
            logger.info("Gemini enricher is not configured. Skipping AI enrichment.")
            return 0

        # Query videos that have no AIEnrichment record
        unenriched_videos = (
            self.db.query(Video)
            .outerjoin(AIEnrichment, Video.id == AIEnrichment.video_id)
            .filter(AIEnrichment.id.is_(None))
            .all()
        )

        if not unenriched_videos:
            logger.info("All videos are already enriched. 0 new videos to process.")
            return 0

        logger.info("Found %d new videos requiring AI enrichment.", len(unenriched_videos))
        enriched_count = 0

        for video in unenriched_videos:
            try:
                enrichment_result = self.enricher.enrich_video_metadata(
                    title=video.title,
                    description=video.description or "",
                )

                db_enrichment = AIEnrichment(
                    video_id=video.id,
                    catchphrase=enrichment_result.catchphrase,
                    synopsis=enrichment_result.synopsis,
                    mood_tags=enrichment_result.mood_tags,
                )
                self.db.add(db_enrichment)
                self.db.commit()
                enriched_count += 1
                logger.info("Successfully enriched video '%s' [%s]", video.title[:25], video.id)

            except Exception as e:
                logger.error("Failed to enrich video %s: %s. Continuing with others.", video.id, e)
                self.db.rollback()

        return enriched_count


def main():
    """CLI Entrypoint for cron execution."""
    parser = argparse.ArgumentParser(description="DAI2FLIX sync batch script.")
    parser.add_argument("--force-unlock", action="store_true", help="Force remove stale lock file")
    args = parser.parse_args()

    settings = get_settings()

    if args.force_unlock:
        lock_path = Path(settings.lock_file_path)
        if lock_path.exists():
            lock_path.unlink()
            logger.info("Lock file %s removed manually.", lock_path)
        sys.exit(0)

    lock = BatchLock(settings.lock_file_path)
    if not lock.acquire():
        logger.warning("Another batch is currently running. Exiting without error.")
        sys.exit(0)

    try:
        logger.info("Starting DAI2FLIX sync batch...")
        init_db()

        youtube_client = None
        if settings.is_youtube_configured():
            youtube_client = YouTubeClient(api_key=settings.youtube_api_key)
        else:
            logger.warning("YOUTUBE_API_KEY is not set or using dummy values.")

        enricher = None
        if settings.is_gemini_configured():
            enricher = MetadataEnricher(api_key=settings.gemini_api_key)
        else:
            logger.warning("GEMINI_API_KEY is not set or using dummy values.")

        with SessionLocal() as db:
            sync_service = SyncService(
                db=db,
                youtube_client=youtube_client,
                enricher=enricher,
            )
            results = sync_service.run()
            logger.info("Sync batch completed: %s", results)

    finally:
        lock.release()


if __name__ == "__main__":
    main()
