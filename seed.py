"""
seed.py — Development seed script.

Creates a complete test fixture:
  org → user (admin) → outlet → platform configs (Swiggy + Zomato)

This mirrors exactly what a real user does through the API so if
the seed data breaks, it means the models are broken too.

Usage:
    python seed.py                         # seed with defaults
    python seed.py --reset                 # drop existing seed data first
    python seed.py --email you@example.com # custom email

The script prints the outlet_id and a ready-to-use curl snippet so
you can immediately start uploading test files.
"""
import asyncio
import argparse
import uuid
from datetime import datetime

from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal
from app.core.auth import hash_password, create_access_token
from app.models.org import Organization, User, Outlet, PlatformConfig, Industry, Plan


# ── Seed defaults ──────────────────────────────────────────────────────────────
# These values are stable across dev machines so fixture CSVs can reference
# the same outlet_id without regenerating.
SEED_ORG_ID     = "00000000-0000-0000-0000-000000000001"
SEED_USER_ID    = "00000000-0000-0000-0000-000000000002"
SEED_OUTLET_ID  = "00000000-0000-0000-0000-000000000003"

DEFAULT_EMAIL    = "dev@bharatvantage.local"
DEFAULT_PASSWORD = "DevPassword123"
DEFAULT_ORG_NAME = "Test Restaurant Group"
DEFAULT_OUTLET   = "Main Outlet — Koregaon Park"


async def seed(email: str, reset: bool) -> None:
    async with AsyncSessionLocal() as db:

        if reset:
            # Delete in reverse FK dependency order
            await db.execute(delete(PlatformConfig).where(
                PlatformConfig.outlet_id == SEED_OUTLET_ID
            ))
            await db.execute(delete(Outlet).where(Outlet.id == SEED_OUTLET_ID))
            await db.execute(delete(User).where(User.id == SEED_USER_ID))
            await db.execute(delete(Organization).where(Organization.id == SEED_ORG_ID))
            await db.commit()
            print("✓ Existing seed data cleared.")

        # ── Check if already seeded ────────────────────────────────────────
        existing = await db.execute(
            select(User).where(User.id == SEED_USER_ID)
        )
        if existing.scalar_one_or_none():
            print("⚠️  Seed data already exists. Run with --reset to recreate.")
            await _print_token(db, email)
            return

        # ── Organization ───────────────────────────────────────────────────
        org = Organization(
            id         = SEED_ORG_ID,
            name       = DEFAULT_ORG_NAME,
            industry   = Industry.RESTAURANT,
            plan       = Plan.FREE,
            created_at = datetime.utcnow(),
        )
        db.add(org)

        # ── User ───────────────────────────────────────────────────────────
        user = User(
            id              = SEED_USER_ID,
            org_id          = SEED_ORG_ID,
            email           = email,
            hashed_password = hash_password(DEFAULT_PASSWORD),
            full_name       = "Dev User",
            is_active       = True,
            created_at      = datetime.utcnow(),
        )
        db.add(user)

        # ── Outlet ─────────────────────────────────────────────────────────
        # Seats and opening_hours are set so RevPASH can be computed in tests.
        outlet = Outlet(
            id            = SEED_OUTLET_ID,
            org_id        = SEED_ORG_ID,
            name          = DEFAULT_OUTLET,
            city          = "Pune",
            seats         = 60,
            opening_hours = 14.0,   # 14 hours/day (11:00 – 01:00)
            gst_rate      = 5.0,
            created_at    = datetime.utcnow(),
            updated_at    = datetime.utcnow(),
        )
        db.add(outlet)

        # ── Platform configs ───────────────────────────────────────────────
        # Commission rates match real 2024 Swiggy/Zomato base rates for restaurants.
        for platform, pct in [("swiggy", 22.0), ("zomato", 25.0)]:
            db.add(PlatformConfig(
                id             = str(uuid.uuid4()),
                outlet_id      = SEED_OUTLET_ID,
                platform       = platform,
                commission_pct = pct,
                active         = True,
                created_at     = datetime.utcnow(),
                updated_at     = datetime.utcnow(),
            ))

        await db.commit()
        print("✓ Seed data created successfully.")
        await _print_token(db, email)


async def _print_token(db, email: str) -> None:
    """Print a JWT token and usage instructions for the seeded user."""
    token = create_access_token(SEED_USER_ID, SEED_ORG_ID)

    print()
    print("─" * 60)
    print("SEED CREDENTIALS")
    print("─" * 60)
    print(f"  Email:      {email}")
    print(f"  Password:   {DEFAULT_PASSWORD}")
    print(f"  Org ID:     {SEED_ORG_ID}")
    print(f"  Outlet ID:  {SEED_OUTLET_ID}")
    print(f"  JWT Token:  {token[:40]}…")
    print()
    print("EXAMPLE — upload a file:")
    print()
    print(f'  curl -X POST http://localhost:8000/api/v1/upload \\')
    print(f'    -H "Authorization: Bearer {token}" \\')
    print(f'    -H "X-Outlet-ID: {SEED_OUTLET_ID}" \\')
    print(f'    -F "files=@your_swiggy_export.csv"')
    print()
    print("EXAMPLE — trigger compute:")
    print()
    print(f'  curl -X POST http://localhost:8000/api/v1/compute/<session_id> \\')
    print(f'    -H "Authorization: Bearer {token}" \\')
    print(f'    -H "X-Outlet-ID: {SEED_OUTLET_ID}"')
    print("─" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed BharatVantage development database.")
    parser.add_argument("--email", default=DEFAULT_EMAIL,
                        help=f"Email for seed user (default: {DEFAULT_EMAIL})")
    parser.add_argument("--reset", action="store_true",
                        help="Delete existing seed data before re-creating it")
    args = parser.parse_args()

    asyncio.run(seed(email=args.email, reset=args.reset))
