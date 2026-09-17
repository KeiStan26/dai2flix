"""Unit tests for CuratorService (Billboard selection and Row synthesis logic)."""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import AIEnrichment, Playlist, PlaylistVideo, Video
from app.schemas import RowType
from app.services.curator import CuratorService


@pytest.fixture
def curator_db():
    """In-memory SQLite database populated with diverse video fixtures."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()

    base_time = datetime.now(timezone.utc)

    # 1. Flagship Video (逃亡生活)
    v1 = Video(
        id="v_escape",
        title="【1週間逃亡生活】全国指名手配から逃げ切れるか #1",
        description="逃亡生活第1話",
        published_at=base_time - timedelta(days=10),
        thumbnail_url="https://img.youtube.com/v_escape.jpg",
        view_count=5000000,
        duration_seconds=3600,
    )
    ai1 = AIEnrichment(
        video_id=v1.id,
        catchphrase="全国が、包囲網。",
        synopsis="7日間の極限逃亡ドキュメンタリー。",
        mood_tags=["#逃亡劇", "#過酷サバイバル"],
    )

    # 2. Psychological Warfare Video (心理戦)
    v2 = Video(
        id="v_psycho",
        title="【極限心理戦】100万円争奪人狼ゲーム",
        description="騙し合いの頂上決戦",
        published_at=base_time - timedelta(days=5),
        thumbnail_url="https://img.youtube.com/v_psycho.jpg",
        view_count=3000000,
        duration_seconds=2400,
    )
    ai2 = AIEnrichment(
        video_id=v2.id,
        catchphrase="信じられる者は、誰もいない。",
        synopsis="嘘と謀略が渦巻く心理バトル。",
        mood_tags=["#極限の心理戦", "#頭脳戦"],
    )

    # 3. Recent small video
    v3 = Video(
        id="v_recent",
        title="だいにぐるーぷサブチャンネル近況報告",
        description="近況報告トーク",
        published_at=base_time - timedelta(days=1),
        thumbnail_url="https://img.youtube.com/v_recent.jpg",
        view_count=100000,
        duration_seconds=600,
    )
    ai3 = AIEnrichment(
        video_id=v3.id,
        catchphrase="日常の舞台裏。",
        synopsis="メンバーが語る制作秘話。",
        mood_tags=["#トーク", "#極限の心理戦"],  # Share tag with v2
    )

    session.add_all([v1, v2, v3, ai1, ai2, ai3])

    # Playlists
    pl1 = Playlist(id="pl_series", title="逃亡生活シリーズ", display_order=1)
    pl2 = Playlist(id="pl_empty", title="空のプレイリスト", display_order=2)
    session.add_all([pl1, pl2])
    session.commit()

    # Associations
    pv1 = PlaylistVideo(playlist_id=pl1.id, video_id=v1.id, position=0)
    session.add(pv1)
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_select_billboard_video_prioritizes_flagship(curator_db):
    """Verify Billboard chooses high-impact flagship video."""
    curator = CuratorService(db=curator_db)
    billboard = curator.select_billboard_video()

    assert billboard is not None
    # v_escape has highest view count and contains '逃亡生活'
    assert billboard.id == "v_escape"
    assert billboard.catchphrase == "全国が、包囲網。"
    assert "#逃亡劇" in billboard.mood_tags


def test_select_billboard_empty_db():
    """Verify Billboard returns None gracefully when database is empty."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()

    curator = CuratorService(db=session)
    billboard = curator.select_billboard_video()
    assert billboard is None
    session.close()


def test_build_content_rows_synthesis(curator_db):
    """Verify synthesis of Recent, Official Playlists, and AI Tag rows."""
    curator = CuratorService(db=curator_db)
    rows = curator.build_content_rows()

    assert len(rows) >= 3

    # Check Recent Row
    recent_row = next((r for r in rows if r.type == RowType.RECENT), None)
    assert recent_row is not None
    assert recent_row.items[0].id == "v_recent"  # Most recent first

    # Check Official Playlist Row
    playlist_row = next((r for r in rows if r.type == RowType.PLAYLIST), None)
    assert playlist_row is not None
    assert playlist_row.title == "逃亡生活シリーズ"
    assert playlist_row.items[0].id == "v_escape"

    # Empty playlist should NOT produce an empty row
    empty_pl_row = next((r for r in rows if r.id == "pl_empty"), None)
    assert empty_pl_row is None

    # Check AI Tag Row (tag shared by v2 and v3: #極限の心理戦)
    tag_rows = [r for r in rows if r.type == RowType.TAG]
    assert len(tag_rows) >= 1
    psycho_row = next((r for r in tag_rows if "極限の心理戦" in r.title), None)
    assert psycho_row is not None
    tag_video_ids = [item.id for item in psycho_row.items]
    assert "v_psycho" in tag_video_ids
    assert "v_recent" in tag_video_ids
