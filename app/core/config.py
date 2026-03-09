"""
config.py — Application settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings
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

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

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
