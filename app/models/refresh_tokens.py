"""
refresh_tokens.py — RefreshToken model.

Stored as SHA-256 hash of the raw token — raw token is never persisted.
One row per issued refresh token. Rows are revoked (not deleted) on rotation
so the audit trail is preserved.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id          = Column(String(36), primary_key=True, default=gen_uuid)
    user_id     = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Raw token is never stored — only the SHA-256 hash.
    # This means a DB breach cannot be used to forge sessions.
    token_hash  = Column(String(64), nullable=False, index=True, unique=True)

    expires_at  = Column(DateTime, nullable=False)
    revoked     = Column(Boolean,  nullable=False, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    revoked_at  = Column(DateTime, nullable=True)
