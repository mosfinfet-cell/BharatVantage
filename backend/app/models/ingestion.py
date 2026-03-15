"""
ingestion.py — Upload sessions, source files, manual entries, stock entries.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def gen_uuid(): return str(uuid.uuid4())


class UploadSession(Base):
    """
    Groups one or more uploaded files into a single analysis session.
    Tracks ingestion status, compute status, and date range of data.
    """
    __tablename__ = "upload_sessions"

    id                  = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id           = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False, index=True)
    vertical            = Column(String(50), nullable=False, default="generic")

    # Status tracking
    ingest_status       = Column(String(20), default="pending")    # pending|running|done|failed
    compute_status      = Column(String(20), default="idle")       # idle|queued|running|done|failed
    compute_job_id      = Column(String(100), nullable=True)       # ARQ job ID — idempotency

    # Data coverage
    date_from           = Column(DateTime, nullable=True)
    date_to             = Column(DateTime, nullable=True)
    source_coverage     = Column(JSON, nullable=True)    # {swiggy: "Jan", petpooja: "Jan-Feb"}

    # Versioning — supports re-upload of corrected data
    supersedes_id       = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=True)

    # Error tracking
    ingest_errors       = Column(JSON, nullable=True)    # [{source, filename, error}]
    error_message       = Column(Text, nullable=True)

    created_at          = Column(DateTime, default=datetime.utcnow)
    computed_at         = Column(DateTime, nullable=True)
    deleted_at          = Column(DateTime, nullable=True)

    outlet          = relationship("Outlet", back_populates="upload_sessions")
    source_files    = relationship("SourceFile", back_populates="session", cascade="all, delete-orphan")
    metric_snapshot = relationship("MetricSnapshot", back_populates="session", uselist=False)


class SourceFile(Base):
    """Individual uploaded file within a session."""
    __tablename__ = "source_files"

    id               = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id       = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=False)

    filename         = Column(String(255), nullable=False)
    original_name    = Column(String(255), nullable=False)
    file_size        = Column(Integer)
    content_hash     = Column(String(64), nullable=False, index=True)   # SHA-256, for dedup
    storage_key      = Column(String(500), nullable=True)               # R2 key

    # Detection results
    detected_source  = Column(String(50))     # swiggy|zomato|petpooja|tally|payroll|generic
    format_version   = Column(String(20))     # e.g. "2024_v1" — for parser version tracking
    confidence       = Column(Float)
    confirmed_source = Column(String(50))     # user-confirmed (may differ from detected)
    data_category    = Column(String(50))     # sales_aggregator|sales_pos|purchases|labor|generic

    # Processing results
    row_count        = Column(Integer, nullable=True)
    records_stored   = Column(Integer, nullable=True)
    parse_status     = Column(String(20), default="pending")   # pending|done|failed|skipped
    parse_error      = Column(Text, nullable=True)

    created_at       = Column(DateTime, default=datetime.utcnow)

    session = relationship("UploadSession", back_populates="source_files")


class ManualEntry(Base):
    """
    Operator-entered data for v1.1 metrics.
    entry_type = 'cash_drawer'    → value = physical drawer amount (₹) for that date
    entry_type = 'platform_rating' → value = rating (1.0-5.0), platform = swiggy|zomato
    """
    __tablename__ = "manual_entries"
    __table_args__ = {"extend_existing": True}

    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id  = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False, index=True)
    entry_type = Column(String(50),  nullable=False)   # cash_drawer | platform_rating
    entry_date = Column(DateTime,    nullable=False)
    platform   = Column(String(30),  nullable=True)    # swiggy|zomato — for ratings only
    value      = Column(Float,       nullable=False)
    created_at = Column(DateTime,    default=datetime.utcnow)

    outlet = relationship("Outlet", back_populates="manual_entries")


class StockEntry(Base):
    """
    Period-specific stock values for inventory variance calculation.
    One row per period. Opening stock of Feb = closing stock of Jan.
    """
    __tablename__ = "stock_entries"

    id                   = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id            = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False, index=True)
    period_from          = Column(DateTime, nullable=False)
    period_to            = Column(DateTime, nullable=False)
    opening_stock_value  = Column(Float, nullable=False, default=0.0)
    closing_stock_value  = Column(Float, nullable=False, default=0.0)
    purchases_value      = Column(Float, nullable=False, default=0.0)
    notes                = Column(Text, nullable=True)
    created_at           = Column(DateTime, default=datetime.utcnow)

    outlet = relationship("Outlet", back_populates="stock_entries")
