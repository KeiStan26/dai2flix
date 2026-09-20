"""SQLAlchemy database models for Daini-group VOD.

Defines schemas for:
- videos: Base video metadata from YouTube Data API
- playlists: YouTube playlists for Row organization
- playlist_videos: Ordered association table between playlists and videos
- ai_enrichments: Netflix-style metadata generated once per video via Gemini LLM
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Video(Base):
    """YouTube Video metadata entity."""

    __tablename__ = "videos"

    id = Column(String(64), primary_key=True, doc="YouTube Video ID (e.g. dQw4w9WgXcQ)")
    title = Column(String(255), nullable=False, doc="Video title")
    description = Column(Text, nullable=True, doc="Original YouTube description")
    published_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Publication timestamp",
    )
    thumbnail_url = Column(String(512), nullable=True, doc="Highest resolution thumbnail URL")
    duration_seconds = Column(Integer, nullable=True, doc="Duration in seconds")
    view_count = Column(BigInteger, nullable=True, default=0, doc="View count")
    is_members_only = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        doc="Whether video is exclusive to channel members",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )

    # Relationships
    ai_enrichment = relationship(
        "AIEnrichment",
        uselist=False,
        back_populates="video",
        cascade="all, delete-orphan",
    )
    playlist_associations = relationship(
        "PlaylistVideo",
        back_populates="video",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Video(id='{self.id}', title='{self.title[:30]}...')>"


class Playlist(Base):
    """YouTube Playlist entity representing categories/rows."""

    __tablename__ = "playlists"

    id = Column(String(64), primary_key=True, doc="YouTube Playlist ID (e.g. PL...)")
    title = Column(String(255), nullable=False, doc="Playlist title")
    description = Column(Text, nullable=True, doc="Playlist description")
    thumbnail_url = Column(String(512), nullable=True, doc="Cover thumbnail URL")
    display_order = Column(Integer, default=0, index=True, doc="Order for UI Row rendering")

    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )

    # Relationships
    video_associations = relationship(
        "PlaylistVideo",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistVideo.position",
    )

    def __repr__(self) -> str:
        return f"<Playlist(id='{self.id}', title='{self.title[:30]}...')>"


class PlaylistVideo(Base):
    """Ordered many-to-many relationship between playlists and videos."""

    __tablename__ = "playlist_videos"

    playlist_id = Column(
        String(64),
        ForeignKey("playlists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    video_id = Column(
        String(64),
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Zero-based ordering index inside the playlist",
    )

    # Relationships
    playlist = relationship("Playlist", back_populates="video_associations")
    video = relationship("Video", back_populates="playlist_associations")

    def __repr__(self) -> str:
        return f"<PlaylistVideo(playlist_id='{self.playlist_id}', video_id='{self.video_id}', pos={self.position})>"


class AIEnrichment(Base):
    """AI-generated Netflix-style metadata (catchphrase, synopsis, mood tags)."""

    __tablename__ = "ai_enrichments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(
        String(64),
        ForeignKey("videos.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    catchphrase = Column(
        String(255),
        nullable=False,
        doc="High-impact Netflix-style catchphrase",
    )
    synopsis = Column(
        Text,
        nullable=False,
        doc="Concise summary (~100 Japanese characters) teasing tension without spoilers",
    )
    mood_tags = Column(
        JSON,
        nullable=False,
        default=list,
        doc="Array of tags e.g. ['#極限の心理戦', '#過酷', '#逃走劇']",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )

    # Relationships
    video = relationship("Video", back_populates="ai_enrichment")

    def __repr__(self) -> str:
        return f"<AIEnrichment(video_id='{self.video_id}', catchphrase='{self.catchphrase[:30]}...')>"
