"""Health check router for monitoring database connectivity and sync status."""

import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from app import __version__
from app.database import get_db
from app.models import AIEnrichment, Playlist, Video
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service and Database Health Check",
    description="Monitors database connectivity, item counts, and latest data synchronization timestamp.",
)
def get_health(db: Session = Depends(get_db)):
    """Perform health and readiness diagnostics."""
    try:
        # Check SQLite connectivity
        db.execute(text("SELECT 1;"))

        # Retrieve counts and latest sync timestamp
        video_count = db.query(func.count(Video.id)).scalar() or 0
        playlist_count = db.query(func.count(Playlist.id)).scalar() or 0

        latest_video_update = db.query(func.max(Video.updated_at)).scalar()
        latest_ai_update = db.query(func.max(AIEnrichment.updated_at)).scalar()

        # Find overall most recent update timestamp
        candidates = [t for t in (latest_video_update, latest_ai_update) if t is not None]
        last_synced_at = max(candidates) if candidates else None

        return HealthResponse(
            status="healthy",
            database="connected",
            video_count=video_count,
            playlist_count=playlist_count,
            last_synced_at=last_synced_at,
            version=__version__,
        )

    except Exception as e:
        logger.error("Health check failed due to database connectivity issue: %s", e)
        # Return 503 Service Unavailable without exposing internal database paths
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "video_count": 0,
                "playlist_count": 0,
                "last_synced_at": None,
                "version": __version__,
            },
        )
