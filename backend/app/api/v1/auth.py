"""
auth.py — POST /api/v1/auth/register
         POST /api/v1/auth/login
         POST /api/v1/auth/refresh
         POST /api/v1/auth/logout

Token strategy:
  - Access token:  15-min JWT returned in response body (used in Authorization header)
  - Refresh token: 30-day random secret, returned in httpOnly cookie named `bv_refresh`
  - On /refresh: old token is revoked, new pair is issued (rotation)
  - On /logout:  all refresh tokens for the user are revoked
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
import re

# Use a permissive email validator instead of pydantic EmailStr.
# EmailStr rejects valid internal domains like .local, .internal, .test.
# Our validator accepts any user@domain.tld format including custom TLDs.
# Pydantic v2 compatible email validator.
# __get_validators__ is removed in v2 — use Annotated + BeforeValidator instead.
from typing import Annotated, Optional
from pydantic import BeforeValidator

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def _validate_email(v: str) -> str:
    if not isinstance(v, str):
        raise ValueError('email must be a string')
    v = v.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError('invalid email format')
    return v

Email = Annotated[str, BeforeValidator(_validate_email)]

from app.core.database import get_db
from app.core.auth import (
    hash_password, verify_password,
    create_access_token,
    create_and_store_refresh_token,
    rotate_refresh_token,
    revoke_all_user_refresh_tokens,
    get_current_user, TokenData,
)
from app.models.org import Organization, User, Outlet, Industry, Plan

router = APIRouter()

# Cookie name — consistent across all auth endpoints
REFRESH_COOKIE = "bv_refresh"


# ── Request / response models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:     Email
    password:  str
    full_name: str
    org_name:  str
    industry:  str = "restaurant"


class LoginRequest(BaseModel):
    email:    Email
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      str
    org_id:       str
    industry:     str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """
    Write refresh token into an httpOnly, Secure, SameSite=Lax cookie.
    httpOnly prevents JS access — XSS cannot steal it.
    SameSite=Lax prevents CSRF on cross-site navigations.
    """
    from app.core.config import settings
    response.set_cookie(
        key       = REFRESH_COOKIE,
        value     = raw_token,
        httponly  = True,
        secure    = not settings.DEBUG,   # HTTPS-only in production
        samesite  = "lax",
        max_age   = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path      = "/api/v1/auth",       # Cookie only sent to auth endpoints
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth")


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
async def register(
    body:     RegisterRequest,
    response: Response,
    db:       AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already registered.")

    try:
        industry = Industry(body.industry)
    except ValueError:
        raise HTTPException(400, f"Invalid industry. Options: {[i.value for i in Industry]}")

    org_id  = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    org = Organization(id=org_id, name=body.org_name, industry=industry, plan=Plan.FREE)
    user = User(
        id              = user_id,
        org_id          = org_id,
        email           = body.email,
        hashed_password = hash_password(body.password),
        full_name       = body.full_name,
    )

    db.add(org)
    db.add(user)
    await db.flush()

    access_token = create_access_token(user_id, org_id)
    raw_refresh  = await create_and_store_refresh_token(db, user_id)
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return AuthResponse(access_token=access_token, user_id=user_id,
                        org_id=org_id, industry=industry.value)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponse)
async def login(
    body:     LoginRequest,
    response: Response,
    db:       AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == body.email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled.")

    org_result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org = org_result.scalar_one_or_none()

    access_token = create_access_token(str(user.id), str(user.org_id))
    raw_refresh  = await create_and_store_refresh_token(db, str(user.id))
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return AuthResponse(
        access_token = access_token,
        user_id      = str(user.id),
        org_id       = str(user.org_id),
        industry     = org.industry.value if org else "generic",
    )


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response:   Response,
    db:         AsyncSession  = Depends(get_db),
    bv_refresh: Optional[str] = Cookie(default=None),
):
    """
    Exchange a valid refresh token cookie for a new access + refresh pair.
    Old token is revoked immediately on use (rotation).
    A stolen token can only be used once before it becomes invalid.
    """
    if not bv_refresh:
        raise HTTPException(status_code=401, detail="No refresh token provided.")

    access_token, new_raw = await rotate_refresh_token(db, bv_refresh)

    from app.core.auth import decode_token
    payload = decode_token(access_token)
    user_id = payload.get("sub")
    org_id  = payload.get("org_id")

    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()

    await db.commit()
    _set_refresh_cookie(response, new_raw)

    return AuthResponse(
        access_token = access_token,
        user_id      = user_id,
        org_id       = org_id,
        industry     = org.industry.value if org else "generic",
    )


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=204)
async def logout(
    response:   Response,
    token_data: TokenData    = Depends(get_current_user),
    db:         AsyncSession = Depends(get_db),
):
    """
    Revoke all refresh tokens for the user. Clear the cookie.
    The 15-min access token expires naturally — no server-side blocklist needed.
    """
    await revoke_all_user_refresh_tokens(db, token_data.user_id)
    await db.commit()
    _clear_refresh_cookie(response)
