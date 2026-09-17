"""Unit tests for sync_batch.py, YouTube client, Gemini enricher, and file lock.

All external API interactions are strictly mocked to eliminate network dependency and avoid spending quota.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AIEnrichment, Playlist, PlaylistVideo, Video
from app.services.enricher import EnrichmentResult, MetadataEnricher
from app.services.youtube import (
    YouTubeClient,
    YouTubePlaylistData,
    YouTubeQuotaExceededError,
    YouTubeVideoData,
    parse_iso8601_duration,
)
from scripts.sync_batch import BatchLock, SyncService


# ------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------
@pytest.fixture
def memory_db():
    """In-memory SQLite database session for unit tests."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()


# ------------------------------------------------------------------------------
# 1. ISO 8601 Duration Parser Tests
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "duration_str, expected_seconds",
    [
        ("PT1H23M45S", 1 * 3600 + 23 * 60 + 45),  # 5025
        ("PT15M30S", 15 * 60 + 30),  # 930
        ("PT45S", 45),
        ("PT2H", 7200),
        ("P1DT2H", 86400 + 7200),
        ("", None),
        (None, None),
        ("INVALID_DURATION", None),
    ],
)
def test_parse_iso8601_duration(duration_str, expected_seconds):
    """Verify robust parsing of ISO 8601 duration strings."""
    assert parse_iso8601_duration(duration_str) == expected_seconds


# ------------------------------------------------------------------------------
# 2. BatchLock (Multi-process prevention) Tests
# ------------------------------------------------------------------------------
def test_batch_lock_lifecycle(tmp_path):
    """Test standard acquisition and release lifecycle of BatchLock."""
    lock_file = tmp_path / "test.lock"
    lock = BatchLock(str(lock_file))

    # 1. Acquire successfully
    assert lock.acquire() is True
    assert lock_file.exists()

    # 2. Second acquisition by simulated concurrent runner should fail
    concurrent_lock = BatchLock(str(lock_file))
    with patch.object(BatchLock, "_is_process_running", return_value=True):
        assert concurrent_lock.acquire() is False

    # 3. Release first lock
    lock.release()
    assert not lock_file.exists()

    # 4. Can acquire again after release
    assert concurrent_lock.acquire() is True
    concurrent_lock.release()


def test_batch_lock_stale_overwriting(tmp_path):
    """Verify that stale or dead process locks are automatically reclaimed."""
    lock_file = tmp_path / "stale.lock"
    # Write a simulated dead lock (PID 999999, old timestamp)
    lock_file.write_text("999999:1000000000.0")

    lock = BatchLock(str(lock_file), stale_seconds=10)
    # Mock _is_process_running to return False
    with patch.object(BatchLock, "_is_process_running", return_value=False):
        assert lock.acquire() is True
        lock.release()


# ------------------------------------------------------------------------------
# 3. YouTubeClient Unit Tests (Mocked HTTP)
# ------------------------------------------------------------------------------
def test_youtube_client_get_channel_playlists(mocker):
    """Test parsing of channel playlists without hitting Google servers."""
    client = YouTubeClient(api_key="AIzaSyDummyKeyTest123")

    mock_response = {
        "items": [
            {
                "id": "PL_sample_01",
                "snippet": {
                    "title": "アメリカ横断の旅",
                    "description": "全米横断企画の再生リスト",
                    "thumbnails": {"high": {"url": "https://img.youtube.com/thumb.jpg"}},
                },
            }
        ]
    }
    mocker.patch.object(client, "_request", return_value=mock_response)

    playlists = client.get_channel_playlists("UC_test_channel")
    assert len(playlists) == 1
    assert playlists[0].id == "PL_sample_01"
    assert playlists[0].title == "アメリカ横断の旅"
    assert playlists[0].thumbnail_url == "https://img.youtube.com/thumb.jpg"


def test_youtube_client_quota_exceeded(mocker):
    """Test handling of 403 quotaExceeded error."""
    client = YouTubeClient(api_key="AIzaSyDummyKeyTest123")

    mock_http_resp = mocker.MagicMock()
    mock_http_resp.status_code = 403
    mock_http_resp.json.return_value = {
        "error": {
            "errors": [{"reason": "quotaExceeded"}],
            "message": "Quota exceeded",
        }
    }

    with patch("httpx.Client.get", return_value=mock_http_resp):
        with pytest.raises(YouTubeQuotaExceededError):
            client.get_channel_playlists("UC_test_channel")


# ------------------------------------------------------------------------------
# 4. MetadataEnricher Fallback & Logic Tests
# ------------------------------------------------------------------------------
def test_metadata_enricher_fallback():
    """Verify that heuristic fallback generates reasonable catchphrases and mood tags."""
    title = "【1週間逃亡生活】警察の包囲網を突破せよ #1"
    desc = "全国を舞台にした逃走劇。だいにぐるーぷの心理戦とサバイバル。"

    fallback = MetadataEnricher.generate_fallback_enrichment(title, desc)
    assert isinstance(fallback, EnrichmentResult)
    assert len(fallback.catchphrase) > 0
    assert len(fallback.synopsis) > 0
    assert "#逃亡劇" in fallback.mood_tags or "#極限の心理戦" in fallback.mood_tags


# ------------------------------------------------------------------------------
# 5. SyncService Differential Sync & Cost Protection Tests
# ------------------------------------------------------------------------------
def test_sync_service_pipeline_and_quota_protection(memory_db):
    """Verify differential sync:

    1. New videos are enriched via LLM.
    2. Subsequent runs with same data do NOT call LLM again (cost/quota protection).
    """
    now = datetime.now(timezone.utc)

    # Mock YouTube Client
    mock_yt = MagicMock(spec=YouTubeClient)
    mock_yt.get_channel_playlists.return_value = [
        YouTubePlaylistData(
            id="PL_main",
            title="大型企画シリーズ",
            description="メイン再生リスト",
            thumbnail_url="https://img.youtube.com/pl.jpg",
        )
    ]
    mock_yt.get_playlist_items.return_value = [
        {
            "video_id": "v101",
            "position": 0,
            "title": "【1週間逃亡生活】第1話",
            "description": "第1話あらすじ",
            "published_at": now,
            "thumbnail_url": "https://img.youtube.com/v101.jpg",
        },
        {
            "video_id": "v102",
            "position": 1,
            "title": "【1週間逃亡生活】第2話",
            "description": "第2話あらすじ",
            "published_at": now,
            "thumbnail_url": "https://img.youtube.com/v102.jpg",
        },
    ]
    mock_yt.get_videos_details.return_value = {
        "v101": YouTubeVideoData(
            id="v101",
            title="【1週間逃亡生活】第1話",
            description="第1話あらすじ",
            published_at=now,
            thumbnail_url="https://img.youtube.com/v101.jpg",
            duration_seconds=3600,
            view_count=1000000,
        ),
        "v102": YouTubeVideoData(
            id="v102",
            title="【1週間逃亡生活】第2話",
            description="第2話あらすじ",
            published_at=now,
            thumbnail_url="https://img.youtube.com/v102.jpg",
            duration_seconds=3700,
            view_count=800000,
        ),
    }

    # Mock Gemini Enricher
    mock_enricher = MagicMock(spec=MetadataEnricher)
    mock_enricher.enrich_video_metadata.return_value = EnrichmentResult(
        catchphrase="全日本を揺るがす逃亡劇",
        synopsis="警察の追跡を逃れ全国を疾走する極限ドキュメンタリー。",
        mood_tags=["#逃亡劇", "#過酷サバイバル"],
    )

    sync_service = SyncService(db=memory_db, youtube_client=mock_yt, enricher=mock_enricher)

    # First Run: Should sync 1 playlist, 2 videos, and enrich 2 videos
    stats_run1 = sync_service.run()
    assert stats_run1["playlists_synced"] == 1
    assert stats_run1["videos_synced"] == 2
    assert stats_run1["videos_enriched"] == 2
    assert mock_enricher.enrich_video_metadata.call_count == 2

    # Verify DB content
    assert memory_db.query(Video).count() == 2
    assert memory_db.query(Playlist).count() == 1
    assert memory_db.query(PlaylistVideo).count() == 2
    assert memory_db.query(AIEnrichment).count() == 2

    # Second Run (Identical Data): Should NOT call enricher again!
    mock_enricher.reset_mock()
    stats_run2 = sync_service.run()
    assert stats_run2["playlists_synced"] == 1
    assert stats_run2["videos_synced"] == 2
    assert stats_run2["videos_enriched"] == 0
    # Strict Quota protection check: LLM must not be called for existing videos
    assert mock_enricher.enrich_video_metadata.call_count == 0
