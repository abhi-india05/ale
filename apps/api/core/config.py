# WHY: D1, TR-INFRA-01 — Configuration with SQLite auto-fallback for zero-config local run
"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    """Application settings with sensible defaults for local development."""

    # Gnani AI
    gnani_api_key_id: str = ""

    # Provider toggle
    mock_providers: bool = True

    # Database
    database_url: str = ""

    # App
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"

    # Open-Meteo harbour coordinates (Malpe default)
    malpe_lat: float = 13.3496
    malpe_lon: float = 74.7039

    # Demo
    demo_otp: str = "4821"

    # CORS
    cors_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ])

    @property
    def use_sqlite(self) -> bool:
        """True when no PostgreSQL DATABASE_URL is configured."""
        return not self.database_url or self.database_url.startswith("sqlite")

    @property
    def effective_database_url(self) -> str:
        """Return configured URL or SQLite fallback."""
        if self.database_url:
            return self.database_url
        return "sqlite+aiosqlite:///ale_voice.db"

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        cors = os.getenv("CORS_ORIGINS", "")
        origins = [o.strip() for o in cors.split(",") if o.strip()] if cors else None
        return cls(
            gnani_api_key_id=os.getenv("GNANI_API_KEY_ID", ""),
            mock_providers=os.getenv("MOCK_PROVIDERS", "true").lower() == "true",
            database_url=os.getenv("DATABASE_URL", ""),
            app_env=os.getenv("APP_ENV", "development"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            malpe_lat=float(os.getenv("MALPE_LAT", "13.3496")),
            malpe_lon=float(os.getenv("MALPE_LON", "74.7039")),
            demo_otp=os.getenv("DEMO_OTP", "4821"),
            cors_origins=origins if origins is not None else [
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:8000",
            ],
        )


# Singleton
settings = Settings.from_env()

