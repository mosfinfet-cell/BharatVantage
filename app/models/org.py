"""
org.py — Organization, Outlet, User, PlatformConfig models.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


def gen_uuid(): return str(uuid.uuid4())


class Industry(str, enum.Enum):
    RESTAURANT = "restaurant"
    GENERIC    = "generic"
    CLOTHING   = "clothing"    # future
    HARDWARE   = "hardware"    # future


class Plan(str, enum.Enum):
    FREE = "free"
    PAID = "paid"


class Organization(Base):
    __tablename__ = "organizations"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name        = Column(String(255), nullable=False)
    industry    = Column(SAEnum(Industry), nullable=False, default=Industry.GENERIC)
    plan        = Column(SAEnum(Plan), nullable=False, default=Plan.FREE)
    created_at  = Column(DateTime, default=datetime.utcnow)
    deleted_at  = Column(DateTime, nullable=True)

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
    """Individual restaurant location. One org may have multiple outlets (future)."""
    __tablename__ = "outlets"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id          = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False)
    name            = Column(String(255), nullable=False)
    city            = Column(String(100), nullable=True)
    seats           = Column(Integer, nullable=True)
    opening_hours   = Column(Float, nullable=True)     # hours per day
    gst_rate        = Column(Float, default=5.0)        # GST % for normalisation
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at      = Column(DateTime, nullable=True)

    org              = relationship("Organization", back_populates="outlets")
    platform_configs = relationship("PlatformConfig", back_populates="outlet", cascade="all, delete-orphan")
    operating_schedule = relationship("OperatingSchedule", back_populates="outlet", cascade="all, delete-orphan")
    upload_sessions  = relationship("UploadSession", back_populates="outlet", cascade="all, delete-orphan")
    item_master      = relationship("ItemMaster", back_populates="outlet", cascade="all, delete-orphan")
    stock_entries    = relationship("StockEntry", back_populates="outlet", cascade="all, delete-orphan")
    manual_entries   = relationship("ManualEntry", back_populates="outlet", cascade="all, delete-orphan")


class PlatformConfig(Base):
    """Per-outlet commission rates for each aggregator platform."""
    __tablename__ = "platform_configs"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id      = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)
    platform       = Column(String(50), nullable=False)   # swiggy | zomato | other
    commission_pct = Column(Float, nullable=False, default=22.0)
    active         = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    outlet = relationship("Outlet", back_populates="platform_configs")


class OperatingSchedule(Base):
    """Per-outlet operating hours per day of week. Used for accurate RevPASH."""
    __tablename__ = "operating_schedules"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id    = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)
    day_of_week  = Column(Integer, nullable=False)   # 0=Monday … 6=Sunday
    is_open      = Column(Boolean, default=True)
    open_time    = Column(String(5), nullable=True)  # "09:00"
    close_time   = Column(String(5), nullable=True)  # "23:00"

    outlet = relationship("Outlet", back_populates="operating_schedule")
