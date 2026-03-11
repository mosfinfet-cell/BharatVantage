"""
auth.py — JWT authentication with org + outlet context.

Token strategy:
  - Access token:  short-lived (15 min), signed JWT, encodes user_id + org_id
  - Refresh token: long-lived (30 days), random secret, stored as SHA-256 hash in DB
  - Outlet is passed per-request via X-Outlet-ID header.
  - Backend validates: user → org → outlet ownership on every request.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    # bcrypt hard limit is 72 bytes — truncate to avoid ValueError on longer passwords
    return pwd_context.hash(password.encode("utf-8")[:72])


def verify_password(plain: str, hashed: str) -> bool:
    # Must truncate the same way as hash_password for comparison to work
    return pwd_context.verify(plain.encode("utf-8")[:72], hashed)


# ── Access tokens (short-lived JWT) ───────────────────────────────────────────

def create_access_token(user_id: str, org_id: str) -> str:
    """
    Issue a short-lived access token (ACCESS_TOKEN_EXPIRE_MINUTES).
    Encodes user_id + org_id only — outlet is passed per-request.
    """
    payload = {
        "sub":    user_id,
        "org_id": org_id,
        "iat":    datetime.utcnow(),
        "exp":    datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")


# ── Refresh tokens (long-lived, stored as hash) ───────────────────────────────

import secrets
import hashlib


def generate_refresh_token() -> str:
    """Generate a cryptographically random 64-char hex refresh token."""
    return secrets.token_hex(32)


def hash_refresh_token(raw_token: str) -> str:
    """SHA-256 hash of the raw refresh token — this is what we store in the DB."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_and_store_refresh_token(
    db: AsyncSession,
    user_id: str,
) -> str:
    """
    Issue a new refresh token, persist its hash, return the raw token.
    The raw token is written into an httpOnly cookie by the auth endpoint.
    """
    from app.models.refresh_tokens import RefreshToken

    raw        = generate_refresh_token()
    token_hash = hash_refresh_token(raw)
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    db.add(RefreshToken(
        user_id    = user_id,
        token_hash = token_hash,
        expires_at = expires_at,
    ))
    # Flush so duplicate-hash violations surface before commit
    await db.flush()
    return raw


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
) -> tuple[str, str]:
    """
    Validate the incoming refresh token, revoke it, issue a new pair.
    Returns (new_access_token, new_raw_refresh_token).

    Raises 401 if the token is invalid, expired, or already revoked.
    Revoking the old token on every rotation means a stolen token can
    only be used once — the second use will fail and alert the system.
    """
    from app.models.refresh_tokens import RefreshToken
    from app.models.org import User

    token_hash = hash_refresh_token(raw_token)

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()

    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token not found.")
    if stored.revoked:
        raise HTTPException(status_code=401, detail="Refresh token already revoked.")
    if stored.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expired.")

    # Revoke old token
    stored.revoked    = True
    stored.revoked_at = datetime.utcnow()

    # Load user for org_id
    user_result = await db.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    # Issue new pair
    access_token   = create_access_token(str(user.id), str(user.org_id))
    new_raw        = await create_and_store_refresh_token(db, str(user.id))
    await db.flush()

    return access_token, new_raw


async def revoke_all_user_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    """Revoke all active refresh tokens for a user. Call on password change or logout."""
    from app.models.refresh_tokens import RefreshToken
    from sqlalchemy import update

    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True, revoked_at=datetime.utcnow())
    )


# ── FastAPI dependencies ──────────────────────────────────────────────────────

class TokenData:
    def __init__(self, user_id: str, org_id: str):
        self.user_id = user_id
        self.org_id  = org_id


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenData:
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    org_id  = payload.get("org_id")
    if not user_id or not org_id:
        raise HTTPException(status_code=401, detail="Malformed token.")
    return TokenData(user_id=user_id, org_id=org_id)


async def get_current_outlet(
    x_outlet_id: Optional[str] = Header(None, alias="X-Outlet-ID"),
    token_data:  TokenData      = Depends(get_current_user),
    db:          AsyncSession   = Depends(get_db),
) -> "Outlet":  # type: ignore — forward ref
    """
    Resolves and validates the outlet from the X-Outlet-ID header.
    Ensures the outlet belongs to the user's org.
    """
    from app.models.org import Outlet  # avoid circular import

    if not x_outlet_id:
        raise HTTPException(status_code=400, detail="X-Outlet-ID header is required.")

    result = await db.execute(
        select(Outlet).where(
            Outlet.id == x_outlet_id,
            Outlet.org_id == token_data.org_id,
            Outlet.deleted_at.is_(None),
        )
    )
    outlet = result.scalar_one_or_none()
    if not outlet:
        raise HTTPException(status_code=404, detail="Outlet not found or access denied.")
    return outlet


# ── Customer ID hashing (DPDP compliance) ─────────────────────────────────────

def hash_customer_id(raw_id: str, outlet_id: str) -> str:
    """
    One-way hash of customer ID scoped to outlet.
    Preserves repeat-customer detection while stripping personal identifiers.
    SHA-256(raw_id + outlet_id_salt)
    """
    if not raw_id or raw_id in ("None", "nan", ""):
        return ""
    salted = f"{raw_id}:{outlet_id}"
    return hashlib.sha256(salted.encode()).hexdigest()[:16]

