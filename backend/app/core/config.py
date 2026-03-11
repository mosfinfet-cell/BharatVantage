"""
config.py — Application settings loaded from environment variables.

CORS note: Railway env vars are plain strings, not JSON lists.
ALLOWED_ORIGINS accepts either:
  - A comma-separated string: "http://localhost:3000,https://bharatvantage.vercel.app"
  - A JSON array string:      '["http://localhost:3000"]'
The validator below handles both formats so Railway and local .env both work.
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import json


class Settings(BaseSettings):
    # App
    APP_NAME: str = "BharatVantage"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15          # short-lived — refreshed via /auth/refresh
    REFRESH_TOKEN_EXPIRE_DAYS: int   = 30          # long-lived refresh token

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/bharatvantage"

    # Redis (ARQ)
    REDIS_URL: str = "redis://localhost:6379"

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "bharatvantage-uploads"
    R2_PUBLIC_URL: str = ""   # optional CDN URL

    # CORS — comma-separated string in Railway env vars
    # e.g. ALLOWED_ORIGINS=http://localhost:3000,https://bharatvantage.vercel.app
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v):
        # Already a list (e.g. from default or test injection)
        if isinstance(v, list):
            return v
        # JSON array string: '["http://localhost:3000"]'
        if isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        # Comma-separated string: "http://localhost:3000,https://foo.vercel.app"
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Upload limits
    MAX_FILE_SIZE_MB: int = 200
    MAX_SESSION_SIZE_MB: int = 500

    # Rate limiting (per org)
    UPLOAD_RATE_LIMIT_PER_HOUR: int = 20   # max uploads per org per hour
    UPLOAD_RATE_LIMIT_PER_DAY:  int = 100  # max uploads per org per day

    # Data retention (days)
    RAW_FILE_RETENTION_DAYS: int = 90
    RECORD_RETENTION_DAYS: int = 365

    # GST default rate for restaurants (%)
    DEFAULT_GST_RATE: float = 5.0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
