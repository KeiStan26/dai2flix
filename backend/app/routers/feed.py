"""Feed router for Netflix-style aggregated video content."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import FeedResponse
from app.services.curator import CuratorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["feed"])


@router.get(
    "/feed",
    response_model=FeedResponse,
    summary="Get Netflix-style curated video feed",
    description=(
        "Returns the top billboard video and horizontal scroll rows combining official "
        "playlists, cross-cutting AI mood tags, and recent uploads."
    ),
)
def get_feed(
    limit_per_row: int = Query(
        20,
        ge=1,
        le=50,
        description="Maximum number of video items to return per horizontal row",
    ),
    db: Session = Depends(get_db),
) -> FeedResponse:
    """Retrieve full curated feed for Netflix UI."""
    try:
        curator = CuratorService(db=db)
        return curator.get_feed(limit_per_row=limit_per_row)
    except Exception as e:
        logger.error("Failed to generate feed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve video feed. Please try again later.",
        )
