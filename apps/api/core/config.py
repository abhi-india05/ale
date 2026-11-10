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

    # Production Authentication & Security
    secret_key: str = "ale-voice-in-malpe-coastal-secret-key-32chars-min-prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_days: int = 30
    otp_expire_minutes: int = 5
    otp_digits: int = 6

    # SMS Gateway Provider (console, fast2sms, twilio)
    sms_provider: str = "console"
    fast2sms_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # Legacy demo fallback (if explicitly requested)
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
            secret_key=os.getenv("SECRET_KEY", "ale-voice-in-malpe-coastal-secret-key-32chars-min-prod"),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expire_days=int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "30")),
            otp_expire_minutes=int(os.getenv("OTP_EXPIRE_MINUTES", "5")),
            otp_digits=int(os.getenv("OTP_DIGITS", "6")),
            sms_provider=os.getenv("SMS_PROVIDER", "console"),
            fast2sms_api_key=os.getenv("FAST2SMS_API_KEY", ""),
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
            demo_otp=os.getenv("DEMO_OTP", "4821"),
            cors_origins=origins if origins is not None else [
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:8000",
            ],
        )


# Singleton
settings = Settings.from_env()

