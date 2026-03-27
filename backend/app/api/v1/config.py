"""
config.py — Outlet configuration endpoints.
POST /api/v1/outlets                — create outlet
GET  /api/v1/outlets                — list outlets for org
PATCH /api/v1/outlets/{id}          — update outlet settings
POST  /api/v1/outlets/{id}/platforms — upsert platform commission config
POST  /api/v1/outlets/{id}/items    — upsert item master entries
POST  /api/v1/outlets/{id}/stock    — submit stock entry for period
"""
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user, get_current_outlet, TokenData
from app.models.org import Outlet, Organization, PlatformConfig
from app.models.records import ItemMaster
from app.models.ingestion import StockEntry, ManualEntry

router = APIRouter()


# ── Outlet CRUD ───────────────────────────────────────────────────────────────

class CreateOutletRequest(BaseModel):
    name:          str
    city:          Optional[str] = None
    seats:         Optional[int] = None
    opening_hours: Optional[float] = None
    gst_rate:      float = 5.0


class OutletResponse(BaseModel):
    id:            str
    name:          str
    city:          Optional[str]
    seats:         Optional[int]
    opening_hours: Optional[float]
    gst_rate:      float
    created_at:    str


@router.post("/outlets", response_model=OutletResponse)
async def create_outlet(
    body:       CreateOutletRequest,
    token_data: TokenData      = Depends(get_current_user),
    db:         AsyncSession   = Depends(get_db),
):
    outlet = Outlet(
        id            = str(uuid.uuid4()),
        org_id        = token_data.org_id,
        name          = body.name,
        city          = body.city,
        seats         = body.seats,
        opening_hours = body.opening_hours,
        gst_rate      = body.gst_rate,
        created_at    = datetime.utcnow(),
    )
    db.add(outlet)
    await db.commit()
    return OutletResponse(
        id            = outlet.id,
        name          = outlet.name,
        city          = outlet.city,
        seats         = outlet.seats,
        opening_hours = outlet.opening_hours,
        gst_rate      = outlet.gst_rate,
        created_at    = outlet.created_at.isoformat(),
    )


@router.get("/outlets", response_model=List[OutletResponse])
async def list_outlets(
    token_data: TokenData    = Depends(get_current_user),
    db:         AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Outlet).where(
            Outlet.org_id == token_data.org_id,
            Outlet.deleted_at.is_(None),
        )
    )
    outlets = result.scalars().all()
    return [
        OutletResponse(
            id            = o.id,
            name          = o.name,
            city          = o.city,
            seats         = o.seats,
            opening_hours = o.opening_hours,
            gst_rate      = o.gst_rate,
            created_at    = o.created_at.isoformat(),
        )
        for o in outlets
    ]


# ── Platform commissions ──────────────────────────────────────────────────────

class PlatformConfigRequest(BaseModel):
    platform:       str    # swiggy | zomato | other
    commission_pct: float


@router.post("/outlets/{outlet_id}/platforms")
async def upsert_platform_config(
    outlet_id: str,
    body:      PlatformConfigRequest,
    outlet:    Outlet       = Depends(get_current_outlet),
    db:        AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformConfig).where(
            PlatformConfig.outlet_id == outlet_id,
            PlatformConfig.platform  == body.platform,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.base_commission_pct = body.commission_pct
        existing.updated_at     = datetime.utcnow()
    else:
        db.add(PlatformConfig(
            id             = str(uuid.uuid4()),
            outlet_id      = outlet_id,
            platform       = body.platform,
            base_commission_pct = body.commission_pct,
        ))
    await db.commit()
    return {"ok": True, "platform": body.platform, "commission_pct": body.commission_pct}


# ── Item master ───────────────────────────────────────────────────────────────

class ItemMasterRequest(BaseModel):
    item_name:     str
    standard_cost: float
    unit:          Optional[str] = None
    category:      Optional[str] = None


@router.post("/outlets/{outlet_id}/items")
async def upsert_item_master(
    outlet_id: str,
    items:     List[ItemMasterRequest],
    outlet:    Outlet       = Depends(get_current_outlet),
    db:        AsyncSession = Depends(get_db),
):
    upserted = 0
    for item in items:
        result = await db.execute(
            select(ItemMaster).where(
                ItemMaster.outlet_id  == outlet_id,
                ItemMaster.item_name  == item.item_name,
                ItemMaster.deleted_at.is_(None),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.standard_cost = item.standard_cost
            existing.unit          = item.unit
            existing.category      = item.category
            existing.updated_at    = datetime.utcnow()
        else:
            db.add(ItemMaster(
                id            = str(uuid.uuid4()),
                outlet_id     = outlet_id,
                item_name     = item.item_name,
                standard_cost = item.standard_cost,
                unit          = item.unit,
                category      = item.category,
            ))
        upserted += 1
    await db.commit()
    return {"ok": True, "upserted": upserted}


# ── Stock entries ─────────────────────────────────────────────────────────────

class StockEntryRequest(BaseModel):
    period_from:         str   # ISO date string
    period_to:           str
    opening_stock_value: float
    closing_stock_value: float
    purchases_value:     float
    notes:               Optional[str] = None


@router.post("/outlets/{outlet_id}/stock")
async def create_stock_entry(
    outlet_id: str,
    body:      StockEntryRequest,
    outlet:    Outlet       = Depends(get_current_outlet),
    db:        AsyncSession = Depends(get_db),
):
    entry = StockEntry(
        id                   = str(uuid.uuid4()),
        outlet_id            = outlet_id,
        period_from          = datetime.fromisoformat(body.period_from),
        period_to            = datetime.fromisoformat(body.period_to),
        opening_stock_value  = body.opening_stock_value,
        closing_stock_value  = body.closing_stock_value,
        purchases_value      = body.purchases_value,
        notes                = body.notes,
    )
    db.add(entry)
    await db.commit()
    return {"ok": True, "stock_entry_id": entry.id}


# ── Manual entries (COGS / labor override) ────────────────────────────────────

class ManualEntryRequest(BaseModel):
    entry_type:  str    # cogs | labor | ad_spend | penalties
    period_from: str
    period_to:   str
    amount:      float
    notes:       Optional[str] = None


@router.post("/outlets/{outlet_id}/manual")
async def create_manual_entry(
    outlet_id:  str,
    body:       ManualEntryRequest,
    outlet:     Outlet       = Depends(get_current_outlet),
    token_data: TokenData    = Depends(get_current_user),
    db:         AsyncSession = Depends(get_db),
):
    entry = ManualEntry(
        id          = str(uuid.uuid4()),
        outlet_id   = outlet_id,
        entry_type  = body.entry_type,
        period_from = datetime.fromisoformat(body.period_from),
        period_to   = datetime.fromisoformat(body.period_to),
        amount      = body.amount,
        notes       = body.notes,
        entered_by  = token_data.user_id,
    )
    db.add(entry)
    await db.commit()
    return {"ok": True, "manual_entry_id": entry.id}
