"""Pydantic schemas for Daini-group VOD API.

Enforces strict input validation and defensive output serialization.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RowType(str, Enum):
    """Categorization type of a feed row."""
    PLAYLIST = "playlist"
    TAG = "tag"
    FEATURED = "featured"
    RECENT = "recent"
    MEMBERSHIP = "membership"
    MEMBERSHIP_TAG = "membership_tag"


class VideoItemResponse(BaseModel):
    """Normalized video item response with integrated AI enrichments."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="YouTube Video ID")
    title: str = Field(..., description="Video title")
    description: Optional[str] = Field(None, description="Original YouTube description")
    published_at: datetime = Field(..., description="Publication date and time (UTC)")
    thumbnail_url: Optional[str] = Field(None, description="Cover thumbnail URL")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    view_count: Optional[int] = Field(0, description="Total view count")
    is_members_only: bool = Field(False, description="Whether video is exclusive to channel members")

    # AI Enrichment fields
    catchphrase: Optional[str] = Field(None, description="Netflix-style high-impact catchphrase")
    synopsis: Optional[str] = Field(None, description="Concise synopsis teasing tension")
    mood_tags: List[str] = Field(default_factory=list, description="Associated mood hashtags")


class RowResponse(BaseModel):
    """Horizontal scroll row of video items for Netflix-style UI."""

    id: str = Field(..., description="Unique row identifier")
    title: str = Field(..., description="Row display title")
    type: RowType = Field(..., description="Row category type")
    is_members_only: bool = Field(False, description="Whether this row belongs to membership section")
    items: List[VideoItemResponse] = Field(..., description="List of video items in this row")
    total_items: int = Field(..., description="Total items available in this category")


class FeedResponse(BaseModel):
    """Aggregated feed response containing hero billboard and content rows."""

    billboard: Optional[VideoItemResponse] = Field(
        None,
        description="Featured hero video displayed at top banner",
    )
    rows: List[RowResponse] = Field(
        default_factory=list,
        description="Curated rows combining official playlists and AI tags",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when feed was generated",
    )


class HealthResponse(BaseModel):
    """Health check status response."""

    status: str = Field(..., description="'healthy' or 'unhealthy'")
    database: str = Field(..., description="'connected' or 'disconnected'")
    video_count: int = Field(..., description="Number of videos in DB")
    playlist_count: int = Field(..., description="Number of playlists in DB")
    last_synced_at: Optional[datetime] = Field(None, description="Latest update timestamp")
    version: str = Field("0.1.0", description="API Version")
