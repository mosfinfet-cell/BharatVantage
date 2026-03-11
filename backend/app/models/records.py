"""
records.py — Domain-separated record tables.
SalesRecord, PurchaseRecord, LaborRecord, ItemMaster.

Indexed on (outlet_id, date, source_type) for fast metric queries.
RLS policies enforce tenant isolation at DB level.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, DateTime,
    ForeignKey, Index, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def gen_uuid(): return str(uuid.uuid4())


class SalesRecord(Base):
    """
    One row per order/transaction from aggregator or POS sources.
    Sources: swiggy, zomato, petpooja, generic_pos
    Amounts stored ex-GST (normalised on ingestion).
    """
    __tablename__ = "sales_records"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id      = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=False)
    outlet_id       = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)

    # Source identification
    source_type     = Column(String(50), nullable=False)   # swiggy|zomato|petpooja|generic
    channel         = Column(String(50), nullable=False)   # swiggy|zomato|dine_in|takeaway|other

    # Temporal
    date            = Column(DateTime, nullable=True, index=True)

    # Order reference
    order_id        = Column(String(100), nullable=True)
    customer_id     = Column(String(16), nullable=True)    # SHA-256 hashed, 16 char prefix

    # Revenue fields (all ex-GST)
    gross_amount    = Column(Float, nullable=True)
    commission      = Column(Float, nullable=True, default=0.0)
    ad_spend        = Column(Float, nullable=True, default=0.0)
    penalty         = Column(Float, nullable=True, default=0.0)
    discount        = Column(Float, nullable=True, default=0.0)
    net_payout      = Column(Float, nullable=True)

    # Item-level fields (from POS sources)
    item_name       = Column(String(255), nullable=True)
    quantity        = Column(Float, nullable=True)
    unit_price      = Column(Float, nullable=True)

    # Dedup flag — True if this row was superseded by aggregator source
    is_deduplicated = Column(Boolean, default=False)

    created_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sales_outlet_date_source", "outlet_id", "date", "source_type"),
        Index("ix_sales_outlet_channel", "outlet_id", "channel"),
        Index("ix_sales_order_id", "outlet_id", "order_id"),
    )


class PurchaseRecord(Base):
    """
    One row per purchase/vendor invoice line item.
    Sources: tally, excel_vendor, manual
    Used for COGS and inventory variance calculation.
    """
    __tablename__ = "purchase_records"

    id                  = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id          = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=False)
    outlet_id           = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)

    source_type         = Column(String(50), nullable=False)   # tally|excel_vendor|manual

    date                = Column(DateTime, nullable=True, index=True)
    reference_id        = Column(String(100), nullable=True)   # voucher no / invoice no

    vendor_name         = Column(String(255), nullable=True)
    ingredient_name     = Column(String(255), nullable=True)
    category            = Column(String(100), nullable=True)   # veg | non-veg | dairy | beverages

    quantity_purchased  = Column(Float, nullable=True)
    unit                = Column(String(50), nullable=True)    # kg | litre | piece
    unit_cost           = Column(Float, nullable=True)
    total_cost          = Column(Float, nullable=True)

    created_at          = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_purchase_outlet_date", "outlet_id", "date"),
        Index("ix_purchase_outlet_ingredient", "outlet_id", "ingredient_name"),
    )


class LaborRecord(Base):
    """
    One row per employee per shift/period from payroll sources.
    Sources: excel_payroll, manual
    Used for labor cost in Prime Cost calculation.
    """
    __tablename__ = "labor_records"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id      = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=False)
    outlet_id       = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)

    source_type     = Column(String(50), nullable=False)   # excel_payroll|manual

    date            = Column(DateTime, nullable=True, index=True)
    period_from     = Column(DateTime, nullable=True)
    period_to       = Column(DateTime, nullable=True)

    employee_name   = Column(String(255), nullable=True)   # not hashed — internal staff data
    role            = Column(String(100), nullable=True)   # chef | waiter | manager
    shift           = Column(String(50), nullable=True)    # morning | evening | night

    hours_worked    = Column(Float, nullable=True)
    wage_per_hour   = Column(Float, nullable=True)
    labor_cost      = Column(Float, nullable=True)         # total for this row

    created_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_labor_outlet_date", "outlet_id", "date"),
    )


class ItemMaster(Base):
    """
    Standard cost per menu item. Required for inventory variance theoretical depletion.
    Owner-maintained. One row per item per outlet.
    """
    __tablename__ = "item_master"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id       = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False)
    item_name       = Column(String(255), nullable=False)
    standard_cost   = Column(Float, nullable=False)        # cost to make one unit
    unit            = Column(String(50), nullable=True)    # plate | portion | piece
    category        = Column(String(100), nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at      = Column(DateTime, nullable=True)

    outlet = relationship("Outlet", back_populates="item_master")

    __table_args__ = (
        Index("ix_item_master_outlet_name", "outlet_id", "item_name"),
    )
