"""
metrics.py — MetricSnapshot and ActionLog models.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, JSON, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def gen_uuid(): return str(uuid.uuid4())


class MetricSnapshot(Base):
    """
    Cached metric computation results for a session.
    Keyed by session_id. One snapshot per compute run.
    result JSON stores the full vertical metric output.
    sufficiency JSON stores per-metric data quality status.
    """
    __tablename__ = "metric_snapshots"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id  = Column(UUID(as_uuid=False), ForeignKey("upload_sessions.id"), nullable=False, unique=True)
    outlet_id   = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False, index=True)
    vertical    = Column(String(50), nullable=False)

    # schema_version tracks the metric engine version that produced this snapshot.
    # Increment CURRENT_SCHEMA_VERSION in jobs.py whenever metric output shape changes.
    # The frontend can use this to show a "recalculate" prompt for stale snapshots.
    schema_version = Column(Integer, nullable=False, default=1)

    computed_at = Column(DateTime, default=datetime.utcnow)
    result      = Column(JSON, nullable=False)       # full vertical MetricResult as dict
    sufficiency = Column(JSON, nullable=False)       # {metric_name: "complete"|"estimated"|"locked"}

    session = relationship("UploadSession", back_populates="metric_snapshot")

    __table_args__ = (
        Index("ix_snapshot_outlet_computed", "outlet_id", "computed_at"),
    )


class ActionLog(Base):
    """
    Immutable log of every action taken from the dashboard.
    dispute_raised | item_flagged | report_exported | manual_entry_added
    """
    __tablename__ = "action_logs"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    outlet_id   = Column(UUID(as_uuid=False), ForeignKey("outlets.id"), nullable=False, index=True)
    session_id  = Column(UUID(as_uuid=False), nullable=True)
    user_id     = Column(UUID(as_uuid=False), nullable=True)

    action_type = Column(String(100), nullable=False)   # raise_dispute|flag_shift|export_report
    payload     = Column(JSON, nullable=True)           # action-specific data
    status      = Column(String(50), default="pending") # pending|done|failed
    result      = Column(JSON, nullable=True)           # output of action (e.g. dispute template)

    created_at  = Column(DateTime, default=datetime.utcnow)
    completed_at= Column(DateTime, nullable=True)
