"""Integration tests for FastAPI endpoints (/api/health, /api/v1/feed, security headers)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AIEnrichment, Playlist, PlaylistVideo, Video


@pytest.fixture
def client_and_session():
    """Create a TestClient with an isolated shared in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSessionLocal()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, session

    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def test_root_endpoint(client_and_session):
    """Test API root welcome endpoint."""
    client, _ = client_and_session
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "DAI2FLIX API"
    assert "/api/health" in data["health"]
    assert "/api/v1/feed" in data["feed"]


def test_security_headers_present(client_and_session):
    """Verify security headers are attached to all responses."""
    client, _ = client_and_session
    response = client.get("/")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "SAMEORIGIN"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_health_check_healthy(client_and_session):
    """Test GET /api/health when database is connected."""
    client, session = client_and_session

    # Seed test data
    now = datetime.now(timezone.utc)
    v = Video(id="v_health_1", title="Test Video", published_at=now)
    p = Playlist(id="pl_health_1", title="Test Playlist")
    session.add_all([v, p])
    session.commit()

    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["video_count"] == 1
    assert data["playlist_count"] == 1
    assert data["last_synced_at"] is not None


def test_health_check_database_failure():
    """Verify GET /api/health gracefully returns 503 without leaking stack trace on DB error."""
    # Simulate DB disconnection by returning a mock session whose execute() fails
    def failing_get_db():
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Simulated DB connection failure")
        yield mock_db

    app.dependency_overrides[get_db] = failing_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "disconnected"
            # Ensure no internal error trace or sensitive string is leaked
            assert "Simulated DB connection failure" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_feed_empty_database(client_and_session):
    """Verify GET /api/v1/feed handles empty database gracefully."""
    client, _ = client_and_session
    response = client.get("/api/v1/feed")
    assert response.status_code == 200
    data = response.json()
    assert data["billboard"] is None
    assert data["rows"] == []
    assert "generated_at" in data


def test_feed_populated_response_structure(client_and_session):
    """Verify GET /api/v1/feed returns properly populated Billboard and Rows."""
    client, session = client_and_session
    now = datetime.now(timezone.utc)

    # Insert Video with AI metadata
    v = Video(
        id="v_fed_01",
        title="【1週間逃亡生活】全国指名手配第1話",
        description="逃亡動画の決定版",
        published_at=now,
        thumbnail_url="https://img.youtube.com/v_fed_01.jpg",
        duration_seconds=3600,
        view_count=2500000,
    )
    ai = AIEnrichment(
        video_id="v_fed_01",
        catchphrase="全日本を揺るがす逃亡劇",
        synopsis="警察から逃げ切る7日間の極限ドキュメンタリー。",
        mood_tags=["#逃亡劇", "#過酷サバイバル"],
    )
    pl = Playlist(id="pl_fed_01", title="逃亡生活シリーズ", display_order=1)
    pv = PlaylistVideo(playlist_id="pl_fed_01", video_id="v_fed_01", position=0)

    session.add_all([v, ai, pl, pv])
    session.commit()

    response = client.get("/api/v1/feed")
    assert response.status_code == 200
    data = response.json()

    # Verify Billboard
    assert data["billboard"] is not None
    assert data["billboard"]["id"] == "v_fed_01"
    assert data["billboard"]["catchphrase"] == "全日本を揺るがす逃亡劇"
    assert "#逃亡劇" in data["billboard"]["mood_tags"]

    # Verify Rows
    rows = data["rows"]
    assert len(rows) >= 2  # Recent row + Playlist row + Tag rows
    playlist_row = next((r for r in rows if r["type"] == "playlist"), None)
    assert playlist_row is not None
    assert playlist_row["title"] == "逃亡生活シリーズ"
    assert len(playlist_row["items"]) == 1
    assert playlist_row["items"][0]["id"] == "v_fed_01"


def test_feed_query_validation(client_and_session):
    """Verify validation on query parameters (422 Unprocessable Entity on invalid inputs)."""
    client, _ = client_and_session

    # limit_per_row < 1
    resp_under = client.get("/api/v1/feed?limit_per_row=0")
    assert resp_under.status_code == 422

    # limit_per_row > 50
    resp_over = client.get("/api/v1/feed?limit_per_row=51")
    assert resp_over.status_code == 422

    # non-integer
    resp_str = client.get("/api/v1/feed?limit_per_row=abc")
    assert resp_str.status_code == 422

    # Valid boundary
    resp_valid = client.get("/api/v1/feed?limit_per_row=50")
    assert resp_valid.status_code == 200
