"""Content curation engine for Daini-group Netflix-style VOD.

Synthesizes:
1. Hero Billboard video selection (highest impact, major series, or newest video).
2. Official YouTube playlist rows (ordered by position).
3. Cross-cutting AI mood tag rows (e.g. #極限の心理戦, #逃亡劇).
4. Recent uploads row.

Enforces defensive coding: prevents N+1 query problems using joinedload/selectinload.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.models import AIEnrichment, Playlist, PlaylistVideo, Video
from app.schemas import FeedResponse, RowResponse, RowType, VideoItemResponse


class CuratorService:
    """Service to assemble rich Netflix-style feed data from database entities."""

    def __init__(self, db: Session):
        self.db = db

    def get_feed(self, limit_per_row: int = 20) -> FeedResponse:
        """Build and return aggregated feed response."""
        billboard = self.select_billboard_video()
        rows = self.build_content_rows(limit_per_row=limit_per_row)

        return FeedResponse(
            billboard=billboard,
            rows=rows,
        )

    def select_billboard_video(self) -> Optional[VideoItemResponse]:
        """Select a premier flagship video for the hero billboard banner.

        Priority:
        1. High-profile flagship videos (titles containing keywords like '逃亡生活', '心理戦', '大型企画') with high view count.
        2. Video with the highest overall view count.
        3. Most recently published video.
        """
        # Load candidate videos with eager AI enrichment to prevent N+1
        candidates = (
            self.db.query(Video)
            .options(joinedload(Video.ai_enrichment))
            .order_by(Video.view_count.desc().nullslast(), Video.published_at.desc())
            .limit(10)
            .all()
        )

        if not candidates:
            # Check if any video exists at all
            # Fallback if no public videos exist yet
            candidates = (
                self.db.query(Video)
                .options(joinedload(Video.ai_enrichment))
                .order_by(Video.view_count.desc())
                .limit(10)
                .all()
            )
            if not candidates:
                return None

        # Prioritize rich series
        priority_keywords = ["アメリカ", "1週間逃亡生活", "刑務所", "無人島", "カジノ", "樹海"]
        for video in candidates:
            if any(k in video.title for k in priority_keywords):
                return self._to_video_response(video)

        # Fallback to top viewed candidate
        return self._to_video_response(candidates[0])

    def build_content_rows(self, limit_per_row: int = 20) -> List[RowResponse]:
        """Generate structured rows: Recent Public Uploads + Membership Archive + Official Playlists + AI Mood Tags."""
        rows: List[RowResponse] = []

        # 1. Recent Public Releases Row (Explicitly exclude members-only to avoid confusion)
        recent_videos = (
            self.db.query(Video)
            .options(joinedload(Video.ai_enrichment))
            .filter(Video.is_members_only.is_(False))
            .order_by(Video.published_at.desc())
            .limit(limit_per_row)
            .all()
        )
        if recent_videos:
            rows.append(
                RowResponse(
                    id="row_recent",
                    title="最新の公開エピソード",
                    type=RowType.RECENT,
                    items=[self._to_video_response(v) for v in recent_videos],
                    total_items=len(recent_videos),
                )
            )

        # 2. Dedicated Membership Archive Row (Curated exclusive content)
        membership_videos = (
            self.db.query(Video)
            .options(joinedload(Video.ai_enrichment))
            .filter(Video.is_members_only.is_(True))
            .order_by(Video.published_at.desc())
            .limit(limit_per_row)
            .all()
        )
        if membership_videos:
            rows.append(
                RowResponse(
                    id="row_membership",
                    title="👑 メンバーシップ限定アーカイブ",
                    type=RowType.MEMBERSHIP,
                    items=[self._to_video_response(v) for v in membership_videos],
                    total_items=len(membership_videos),
                )
            )

        # 3. Official Playlist Rows
        playlists = (
            self.db.query(Playlist)
            .order_by(Playlist.display_order.asc(), Playlist.created_at.asc())
            .all()
        )

        for pl in playlists:
            # Skip internal UUMO playlist here since it's already rendered as row_membership
            if pl.id.startswith("UUMO"):
                continue

            # Query associated videos in order with eager load
            playlist_entries = (
                self.db.query(PlaylistVideo)
                .filter(PlaylistVideo.playlist_id == pl.id)
                .join(Video, PlaylistVideo.video_id == Video.id)
                .options(joinedload(PlaylistVideo.video).joinedload(Video.ai_enrichment))
                .order_by(PlaylistVideo.position.asc())
                .limit(limit_per_row)
                .all()
            )

            if playlist_entries:
                items = [self._to_video_response(entry.video) for entry in playlist_entries if entry.video]
                if items:
                    rows.append(
                        RowResponse(
                            id=f"pl_{pl.id}",
                            title=pl.title,
                            type=RowType.PLAYLIST,
                            items=items,
                            total_items=len(items),
                        )
                    )

        # 4. AI Mood Tag Rows (Cross-cutting categories based on AI tags)
        tag_rows = self._build_ai_tag_rows(limit_per_row=limit_per_row)
        rows.extend(tag_rows)

        return rows

    def _build_ai_tag_rows(self, limit_per_row: int = 20) -> List[RowResponse]:
        """Collect videos by common mood tags and construct dynamic category rows."""
        # Query all videos that have AI enrichments
        videos_with_ai = (
            self.db.query(Video)
            .join(AIEnrichment, Video.id == AIEnrichment.video_id)
            .options(joinedload(Video.ai_enrichment))
            .order_by(Video.published_at.desc())
            .all()
        )

        tag_to_videos: Dict[str, List[Video]] = defaultdict(list)
        for video in videos_with_ai:
            if video.ai_enrichment and video.ai_enrichment.mood_tags:
                tags = video.ai_enrichment.mood_tags
                if isinstance(tags, list):
                    for tag in tags:
                        if isinstance(tag, str) and tag.strip():
                            clean_tag = tag.strip()
                            tag_to_videos[clean_tag].append(video)

        # Sort tags by popularity (video count descending)
        curated_tag_rows: List[RowResponse] = []
        # Filter for tags that group at least 2 videos to ensure meaningful rows
        sorted_tags = sorted(
            [(t, vids) for t, vids in tag_to_videos.items() if len(vids) >= 1],
            key=lambda x: len(x[1]),
            reverse=True,
        )

        # Limit to top 5 most prominent AI tag categories
        for tag, vids in sorted_tags[:5]:
            display_title = tag.lstrip("#")
            row_id = f"tag_{abs(hash(tag))}"
            items = [self._to_video_response(v) for v in vids[:limit_per_row]]

            curated_tag_rows.append(
                RowResponse(
                    id=row_id,
                    title=f"カテゴリー: {display_title}",
                    type=RowType.TAG,
                    items=items,
                    total_items=len(vids),
                )
            )

        return curated_tag_rows

    @staticmethod
    def _to_video_response(video: Optional[Video]) -> Optional[VideoItemResponse]:
        """Convert a Video SQLAlchemy model instance into VideoItemResponse Pydantic schema."""
        if not video:
            return None

        catchphrase = None
        synopsis = None
        mood_tags = []

        if video.ai_enrichment:
            catchphrase = video.ai_enrichment.catchphrase
            synopsis = video.ai_enrichment.synopsis
            raw_tags = video.ai_enrichment.mood_tags
            if isinstance(raw_tags, list):
                mood_tags = [str(t) for t in raw_tags]

        return VideoItemResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            published_at=video.published_at,
            thumbnail_url=video.thumbnail_url,
            duration_seconds=video.duration_seconds,
            view_count=video.view_count or 0,
            is_members_only=bool(video.is_members_only),
            catchphrase=catchphrase,
            synopsis=synopsis,
            mood_tags=mood_tags,
        )
