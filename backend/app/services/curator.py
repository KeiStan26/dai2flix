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
        Explicitly excludes members-only videos from the public billboard.
        """
        # Load candidate public videos with eager AI enrichment to prevent N+1
        candidates = (
            self.db.query(Video)
            .filter(Video.is_members_only.is_(False))
            .options(joinedload(Video.ai_enrichment))
            .order_by(Video.view_count.desc().nullslast(), Video.published_at.desc())
            .limit(10)
            .all()
        )

        if not candidates:
            # Fallback to any public video
            candidates = (
                self.db.query(Video)
                .filter(Video.is_members_only.is_(False))
                .options(joinedload(Video.ai_enrichment))
                .order_by(Video.view_count.desc().nullslast())
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

        # 1. Recent Public Releases Row (Strictly public only)
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
                    is_members_only=False,
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
                    title="👑 最新メンバーシップ限定アーカイブ",
                    type=RowType.MEMBERSHIP,
                    is_members_only=True,
                    items=[self._to_video_response(v) for v in membership_videos],
                    total_items=len(membership_videos),
                )
            )

        # 3. Official Playlist Rows (Strictly public only)
        playlists = (
            self.db.query(Playlist)
            .order_by(Playlist.display_order.asc(), Playlist.created_at.asc())
            .all()
        )

        for pl in playlists:
            # Skip internal UUMO playlist here since it's already rendered as row_membership
            if pl.id.startswith("UUMO"):
                continue

            # Query associated videos in order with eager load, strictly excluding members-only videos
            playlist_entries = (
                self.db.query(PlaylistVideo)
                .filter(PlaylistVideo.playlist_id == pl.id)
                .join(Video, PlaylistVideo.video_id == Video.id)
                .filter(Video.is_members_only.is_(False))
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
                            is_members_only=False,
                            items=items,
                            total_items=len(items),
                        )
                    )

        # 4. Public AI Mood Tag Rows (Strictly is_members_only == False)
        public_tag_rows = self._build_ai_tag_rows(
            is_members_only=False,
            limit_per_row=limit_per_row,
            max_tags=6,
        )
        rows.extend(public_tag_rows)

        # 5. Membership AI Mood Tag Rows (Strictly is_members_only == True)
        membership_tag_rows = self._build_ai_tag_rows(
            is_members_only=True,
            limit_per_row=limit_per_row,
            max_tags=6,
        )
        rows.extend(membership_tag_rows)

        return rows

    def _build_ai_tag_rows(
        self,
        is_members_only: bool,
        limit_per_row: int = 20,
        max_tags: int = 6,
    ) -> List[RowResponse]:
        """Collect videos by common mood tags and construct dynamic category rows separated by access level."""
        # Query videos matching the exact access level that have AI enrichments
        videos_with_ai = (
            self.db.query(Video)
            .join(AIEnrichment, Video.id == AIEnrichment.video_id)
            .filter(Video.is_members_only.is_(is_members_only))
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

        # For members-only videos: supplement with keyword categorization (behind the scenes, unreleased, live, talk)
        if is_members_only:
            all_mo_videos = (
                self.db.query(Video)
                .filter(Video.is_members_only.is_(True))
                .options(joinedload(Video.ai_enrichment))
                .order_by(Video.published_at.desc())
                .all()
            )
            mo_categories: List[Tuple[str, List[str]]] = [
                ("メイキング・裏側", ["メイキング", "裏側", "オフショット", "制作", "裏話", "撮影"]),
                ("未公開・NGシーン", ["未公開", "ng", "カット", "没", "ディレクターズ"]),
                ("生配信アーカイブ", ["生配信", "live", "配信", "ライブ"]),
                ("トーク・企画反省会", ["トーク", "会議", "反省会", "雑談", "ラジオ", "振り返り", "感想"]),
            ]
            for cat_title, kw_list in mo_categories:
                matched = [
                    v for v in all_mo_videos
                    if any(kw in (v.title or "").lower() or kw in (v.description or "").lower() for kw in kw_list)
                ]
                if matched:
                    tag_to_videos[cat_title] = matched

        # Sort tags by popularity (video count descending)
        curated_tag_rows: List[RowResponse] = []
        sorted_tags = sorted(
            [(t, vids) for t, vids in tag_to_videos.items() if len(vids) >= 1],
            key=lambda x: len(x[1]),
            reverse=True,
        )

        prefix_id = "mem_tag_" if is_members_only else "tag_"
        row_type = RowType.MEMBERSHIP_TAG if is_members_only else RowType.TAG

        for tag, vids in sorted_tags[:max_tags]:
            display_title = tag.lstrip("#")
            row_id = f"{prefix_id}{abs(hash(tag))}"
            items = [self._to_video_response(v) for v in vids[:limit_per_row]]

            title_str = f"👑 限定カテゴリー: {display_title}" if is_members_only else f"カテゴリー: {display_title}"

            curated_tag_rows.append(
                RowResponse(
                    id=row_id,
                    title=title_str,
                    type=row_type,
                    is_members_only=is_members_only,
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
