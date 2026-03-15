"""
org.py — Organization, Outlet, User, PlatformConfig models.

v1.1: Added OutletType enum + new Outlet fields.
Note: gst_rate column already exists in DB as 'gst_rate'.
      gst_rate_pct is the new v1.1 column added by migration 0002.
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean,
    DateTime, ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def gen_uuid(): return str(uuid.uuid4())


class Industry(str, enum.Enum):
    RESTAURANT    = "restaurant"
    GENERIC       = "generic"
    CLOTHING      = "clothing"
    HARDWARE      = "hardware"


class Plan(str, enum.Enum):
    FREE = "free"
    PAID = "paid"


class OutletType(str, enum.Enum):
    """
    Controls which metric groups are computed and which UI sections rendered.
      dine_in       → M1–M8 only (no aggregator data)
      hybrid        → Full 3-layer dashboard (dine-in tab + online tab)
      cloud_kitchen → Online-only metrics
    """
    DINE_IN       = "dine_in"
    HYBRID        = "hybrid"
    CLOUD_KITCHEN = "cloud_kitchen"


class Organization(Base):
    __tablename__ = "organizations"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name       = Column(String(255), nullable=False)
    industry   = Column(SAEnum(Industry, values_callable=lambda x: [e.value for e in x]),
                        nullable=False, default=Industry.RESTAURANT)
    plan       = Column(SAEnum(Plan, values_callable=lambda x: [e.value for e in x]),
                        nullable=False, default=Plan.FREE)
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    users   = relationship("User",   back_populates="org",  cascade="all, delete-orphan")
    outlets = relationship("Outlet", back_populates="org",  cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id          = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name       = Column(String(255), nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    deleted_at      = Column(DateTime, nullable=True)

    org = relationship("Organization", back_populates="users")


class Outlet(Base):
    __tablename__ = "outlets"
    __table_args__ = {"extend_existing": True}

    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id      = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False)
    name        = Column(String(255), nullable=False)
    city        = Column(String(100), nullable=True)

    # outlet_type: v1.1 — stored as VARCHAR(20) in DB (not native enum)
    outlet_type = Column(String(20), nullable=False, default="hybrid")

    # Physical config
    seats         = Column(Integer, nullable=True)
    opening_hours = Column(Float,   nullable=True)

    # Tax — original column is 'gst_rate', v1.1 adds 'gst_rate_pct'
    gst_rate     = Column(Float, default=5.0)   # original column
    gst_rate_pct = Column(Float, default=5.0)   # v1.1 column added by migration 0002

    # Packaging cost tiers (v1.1)
    packaging_cost_tier1 = Column(Float,   default=12.0)
    packaging_cost_tier2 = Column(Float,   default=20.0)
    packaging_cost_tier3 = Column(Float,   default=35.0)
    packaging_configured = Column(Boolean, default=False)

    # Fixed costs for cloud kitchen break-even
    monthly_rent      = Column(Float, nullable=True)
    monthly_utilities = Column(Float, nullable=True)

    # Settlement cycles (days)
    settlement_cycle_swiggy = Column(Integer, default=7)
    settlement_cycle_zomato = Column(Integer, default=7)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    org                = relationship("Organization",      back_populates="outlets")
    platform_configs   = relationship("PlatformConfig",    back_populates="outlet",
                                      cascade="all, delete-orphan")
    operating_schedule = relationship("OperatingSchedule", back_populates="outlet",
                                      cascade="all, delete-orphan")
    upload_sessions    = relationship("UploadSession",     back_populates="outlet",
                                      cascade="all, delete-orphan")
    item_master        = relationship("ItemMaster",        back_populates="outlet",
                                      cascade="all, delete-orphan")
    manual_entries     = relationship("ManualEntry",       back_populates="outlet",
                                      cascade="all, delete-orphan")


class PlatformConfig(Base):
    __tablename__ = "platform_configs"
    __table_args__ = {"extend_existing": True}

    id                    = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id             = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)
    platform              = Column(String(50),  nullable=False)
    base_commission_pct   = Column(Float,        nullable=True)
    settlement_cycle_days = Column(Integer,      default=7)
    is_active             = Column(Boolean,      default=True)
    created_at            = Column(DateTime,     default=datetime.utcnow)

    outlet = relationship("Outlet", back_populates="platform_configs")


class OperatingSchedule(Base):
    __tablename__ = "operating_schedules"
    __table_args__ = {"extend_existing": True}

    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id   = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)
    day_of_week = Column(Integer,    nullable=False)
    open_time   = Column(String(5),  nullable=True)
    close_time  = Column(String(5),  nullable=True)
    is_closed   = Column(Boolean,    default=False)
    created_at  = Column(DateTime,   default=datetime.utcnow)

    outlet = relationship("Outlet", back_populates="operating_schedule")
