"""Application configuration management using pydantic-settings.

Enforces strict type safety and guarantees that secrets are never hardcoded.
"""

from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # External APIs
    youtube_api_key: str = ""
    gemini_api_key: str = ""

    # Target YouTube Channel / Playlists
    channel_id: str = "UC_SAMPLE_DAINI_GROUP_CHANNEL_ID"
    sync_playlist_ids: str = ""  # Comma-separated playlist IDs

    # Storage & Locks
    database_url: str = "sqlite:///./dai2flix.db"
    lock_file_path: str = "./sync.lock"

    # Server & Logging
    host: str = "127.0.0.1"
    port: int = 8008
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def playlist_id_list(self) -> List[str]:
        """Parse comma-separated playlist IDs into a clean list."""
        if not self.sync_playlist_ids:
            return []
        return [pid.strip() for pid in self.sync_playlist_ids.split(",") if pid.strip()]

    def is_youtube_configured(self) -> bool:
        """Check if YouTube API key is configured."""
        return bool(self.youtube_api_key and not self.youtube_api_key.startswith("your_"))

    def is_gemini_configured(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.gemini_api_key and not self.gemini_api_key.startswith("your_"))


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
