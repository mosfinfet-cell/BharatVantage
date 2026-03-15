"""
records.py — SalesRecord, PurchaseRecord, LaborRecord, ItemMaster, ManualEntry, StockEntry.

v1.1 changes to SalesRecord:
  - payment_method, settlement_date, settled, reason_code, service_period, gst_on_commission

New table: ManualEntry (cash_drawer and platform_rating entries)
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def gen_uuid(): return str(uuid.uuid4())


RECOVERABLE_REASON_CODES = {
    "swiggy": {"RIDER_UNAVAILABLE","PLATFORM_DELAY","INCORRECT_DEDUCTION","LATE_DELIVERY_PLATFORM","SYSTEM_CANCELLATION"},
    "zomato": {"RIDER_ISSUE","SYSTEM_ERROR","WRONG_CHARGE","PLATFORM_CANCELLATION","INCORRECT_PENALTY"},
}
NON_RECOVERABLE_REASON_CODES = {
    "swiggy": {"LATE_PREPARATION","CANCELLATION_BY_RESTAURANT","LOW_RATING","QUALITY_COMPLAINT","WRONG_ORDER"},
    "zomato": {"LATE_PREP","RESTAURANT_CANCEL","QUALITY_ISSUE","MISSING_ITEM","WRONG_ITEM"},
}


def classify_penalty(source_type: str, reason_code) -> str:
    if not reason_code:
        return "review_required"
    src  = source_type.lower()
    code = reason_code.upper()
    if src in RECOVERABLE_REASON_CODES and code in RECOVERABLE_REASON_CODES[src]:
        return "recoverable"
    if src in NON_RECOVERABLE_REASON_CODES and code in NON_RECOVERABLE_REASON_CODES[src]:
        return "non_recoverable"
    return "review_required"


class SalesRecord(Base):
    __tablename__ = "sales_records"

    id               = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id       = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=False)
    outlet_id        = Column(UUID(as_uuid=False), ForeignKey("outlets.id"),         nullable=False)
    source_type      = Column(String(50),  nullable=False)
    channel          = Column(String(50),  nullable=False)
    date             = Column(DateTime,    nullable=True, index=True)
    service_period   = Column(String(20),  nullable=True)
    order_id         = Column(String(100), nullable=True)
    customer_id      = Column(String(16),  nullable=True)
    gross_amount     = Column(Float,       nullable=True)
    commission       = Column(Float,       nullable=True, default=0.0)
    gst_on_commission= Column(Float,       nullable=True, default=0.0)
    ad_spend         = Column(Float,       nullable=True, default=0.0)
    penalty          = Column(Float,       nullable=True, default=0.0)
    discount         = Column(Float,       nullable=True, default=0.0)
    net_payout       = Column(Float,       nullable=True)
    item_name        = Column(String(255), nullable=True)
    quantity         = Column(Float,       nullable=True)
    unit_price       = Column(Float,       nullable=True)
    payment_method   = Column(String(20),  nullable=True)
    settlement_date  = Column(DateTime,    nullable=True)
    settled          = Column(Boolean,     default=False)
    reason_code      = Column(String(100), nullable=True)
    penalty_state    = Column(String(20),  nullable=True)
    is_deduplicated  = Column(Boolean,     default=False)
    created_at       = Column(DateTime,    default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sales_outlet_date_source",   "outlet_id", "date", "source_type"),
        Index("ix_sales_outlet_channel",       "outlet_id", "channel"),
        Index("ix_sales_order_id",             "outlet_id", "order_id"),
        Index("ix_sales_outlet_settled",       "outlet_id", "settled"),
        Index("ix_sales_outlet_penalty_state", "outlet_id", "penalty_state"),
        {"extend_existing": True},
    )


class PurchaseRecord(Base):
    __tablename__ = "purchase_records"

    id                  = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id          = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=False)
    outlet_id           = Column(UUID(as_uuid=False), ForeignKey("outlets.id"),         nullable=False)
    source_type         = Column(String(50),  nullable=False)
    date                = Column(DateTime,    nullable=True, index=True)
    reference_id        = Column(String(100), nullable=True)
    vendor_name         = Column(String(255), nullable=True)
    ingredient_name     = Column(String(255), nullable=True)
    category            = Column(String(100), nullable=True)
    quantity_purchased  = Column(Float,       nullable=True)
    unit                = Column(String(50),  nullable=True)
    unit_cost           = Column(Float,       nullable=True)
    total_cost          = Column(Float,       nullable=True)
    created_at          = Column(DateTime,    default=datetime.utcnow)

    __table_args__ = (
        Index("ix_purchase_outlet_date",       "outlet_id", "date"),
        Index("ix_purchase_outlet_ingredient", "outlet_id", "ingredient_name"),
        {"extend_existing": True},
    )


class LaborRecord(Base):
    """
    INDIA MODEL: Monthly salaries only. Do NOT compute hourly.
    labor_cost = total monthly salary for this employee.
    staff_cost_pct = SUM(labor_cost) / net_revenue * 100
    """
    __tablename__ = "labor_records"

    id            = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id    = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=False)
    outlet_id     = Column(UUID(as_uuid=False), ForeignKey("outlets.id"),         nullable=False)
    source_type   = Column(String(50),  nullable=False)
    date          = Column(DateTime,    nullable=True)
    period_from   = Column(DateTime,    nullable=True)
    period_to     = Column(DateTime,    nullable=True)
    employee_name = Column(String(255), nullable=True)
    role          = Column(String(100), nullable=True)
    shift         = Column(String(50),  nullable=True)
    labor_cost    = Column(Float,       nullable=True)
    hours_worked  = Column(Float,       nullable=True)
    wage_per_hour = Column(Float,       nullable=True)
    created_at    = Column(DateTime,    default=datetime.utcnow)

    __table_args__ = (
        Index("ix_labor_outlet_date", "outlet_id", "date"),
        Index("ix_labor_outlet_role", "outlet_id", "role"),
        {"extend_existing": True},
    )


class ItemMaster(Base):
    """Standard cost per menu item. Metric H-O7 locked until >= 5 items."""
    __tablename__ = "item_master"

    id            = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id     = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)
    item_name     = Column(String(255), nullable=False)
    standard_cost = Column(Float,       nullable=False)
    unit          = Column(String(50),  nullable=True)
    category      = Column(String(100), nullable=True)
    is_active     = Column(Boolean,     default=True)
    created_at    = Column(DateTime,    default=datetime.utcnow)
    updated_at    = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at    = Column(DateTime,    nullable=True)

    outlet = relationship("Outlet", back_populates="item_master")

    __table_args__ = (
        Index("ix_item_master_outlet_name", "outlet_id", "item_name"),
        {"extend_existing": True},
    )

