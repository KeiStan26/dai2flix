"""Tests for database initialization, WAL mode, models, and constraints."""

import os
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, set_sqlite_pragma
from app.models import AIEnrichment, Playlist, PlaylistVideo, Video


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary SQLite database with WAL mode and pragmas applied."""
    db_file = tmp_path / "test_daini_vod.db"
    db_url = f"sqlite:///{db_file}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, future=True)
    event.listen(engine, "connect", set_sqlite_pragma)

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

    session = TestingSessionLocal()
    try:
        yield session, engine
    finally:
        session.close()
        engine.dispose()


def test_sqlite_pragmas_and_wal_mode(test_db):
    """Verify that WAL mode and key SQLite PRAGMAs are correctly enabled."""
    _, engine = test_db
    with engine.connect() as conn:
        journal_mode = conn.exec_driver_sql("PRAGMA journal_mode;").scalar()
        # In file-based SQLite, WAL should be active
        assert journal_mode.lower() == "wal"

        foreign_keys = conn.exec_driver_sql("PRAGMA foreign_keys;").scalar()
        assert foreign_keys == 1

        busy_timeout = conn.exec_driver_sql("PRAGMA busy_timeout;").scalar()
        assert busy_timeout == 5000


def test_video_and_ai_enrichment_creation(test_db):
    """Test creating a video and its corresponding 1-to-1 AIEnrichment entity."""
    session, _ = test_db

    now = datetime.now(timezone.utc)
    video = Video(
        id="vid_test_01",
        title="【1週間逃亡生活】日本全国で警察から逃げ切れるか",
        description="全国を舞台にした1週間の逃亡劇。だいにぐるーぷ最大の大型企画。",
        published_at=now,
        thumbnail_url="https://i.ytimg.com/vi/vid_test_01/maxresdefault.jpg",
        duration_seconds=3600,
        view_count=5000000,
    )
    session.add(video)
    session.commit()

    # Query video back
    saved_video = session.query(Video).filter_by(id="vid_test_01").first()
    assert saved_video is not None
    assert saved_video.title.startswith("【1週間逃亡生活】")

    # Add AI enrichment
    enrichment = AIEnrichment(
        video_id=video.id,
        catchphrase="日本中が、敵になる。",
        synopsis="7日間にわたる極限の追跡劇。全国に張り巡らされた包囲網を突破できるか。",
        mood_tags=["#逃亡劇", "#過酷サバイバル", "#大型企画"],
    )
    session.add(enrichment)
    session.commit()

    # Verify relationship
    assert saved_video.ai_enrichment is not None
    assert saved_video.ai_enrichment.catchphrase == "日本中が、敵になる。"
    assert "#逃亡劇" in saved_video.ai_enrichment.mood_tags


def test_playlist_and_ordered_association(test_db):
    """Test playlist creation and ordered video associations."""
    session, _ = test_db
    now = datetime.now(timezone.utc)

    # Create Playlist
    playlist = Playlist(
        id="PL_series_01",
        title="1週間逃亡生活シリーズ",
        description="逃亡生活シリーズ全エピソード",
        display_order=1,
    )
    session.add(playlist)

    # Create Videos
    v1 = Video(id="v1", title="Episode 1", published_at=now)
    v2 = Video(id="v2", title="Episode 2", published_at=now)
    session.add_all([v1, v2])
    session.commit()

    # Add associations with positions
    pv1 = PlaylistVideo(playlist_id=playlist.id, video_id=v1.id, position=0)
    pv2 = PlaylistVideo(playlist_id=playlist.id, video_id=v2.id, position=1)
    session.add_all([pv1, pv2])
    session.commit()

    # Verify playlist ordering
    saved_playlist = session.query(Playlist).filter_by(id="PL_series_01").first()
    assert len(saved_playlist.video_associations) == 2
    assert saved_playlist.video_associations[0].video_id == "v1"
    assert saved_playlist.video_associations[1].video_id == "v2"


def test_cascade_deletion(test_db):
    """Verify that deleting a video cascades and removes AIEnrichment and PlaylistVideo."""
    session, _ = test_db
    now = datetime.now(timezone.utc)

    p = Playlist(id="PL_casc", title="Casc Playlist")
    v = Video(id="v_casc", title="Casc Video", published_at=now)
    session.add_all([p, v])
    session.commit()

    pv = PlaylistVideo(playlist_id=p.id, video_id=v.id, position=0)
    ai = AIEnrichment(
        video_id=v.id,
        catchphrase="CP",
        synopsis="Synopsis",
        mood_tags=["#tag"],
    )
    session.add_all([pv, ai])
    session.commit()

    # Delete video
    session.delete(v)
    session.commit()

    # Verify cascade deletion
    assert session.query(AIEnrichment).filter_by(video_id="v_casc").first() is None
    assert session.query(PlaylistVideo).filter_by(video_id="v_casc").first() is None
    # Playlist should remain
    assert session.query(Playlist).filter_by(id="PL_casc").first() is not None
