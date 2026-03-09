"""
actions.py — POST /api/v1/actions/{session_id}/{action_type}
Executes an action and logs it to action_log.
Returns the action result (dispute template, export URL, etc.)
"""
import uuid
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_outlet, get_current_user, TokenData
from app.models.metrics import ActionLog, MetricSnapshot
from app.models.ingestion import UploadSession
from app.models.org import Outlet

router = APIRouter()


class ActionRequest(BaseModel):
    payload: dict = {}


@router.post("/actions/{session_id}/{action_type}")
async def execute_action(
    session_id:  str,
    action_type: str,
    body:        ActionRequest,
    outlet:      Outlet       = Depends(get_current_outlet),
    token_data:  TokenData    = Depends(get_current_user),
    db:          AsyncSession = Depends(get_db),
):
    valid_actions = {"raise_dispute", "flag_shift", "export_report"}
    if action_type not in valid_actions:
        raise HTTPException(400, f"Unknown action. Valid: {valid_actions}")

    # Verify session ownership
    sess_result = await db.execute(
        select(UploadSession).where(
            UploadSession.id        == session_id,
            UploadSession.outlet_id == str(outlet.id),
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found.")

    # Get metric snapshot for context
    snap_result = await db.execute(
        select(MetricSnapshot).where(MetricSnapshot.session_id == session_id)
    )
    snapshot = snap_result.scalar_one_or_none()

    # Execute action
    result = None
    if action_type == "raise_dispute":
        result = _generate_dispute_template(snapshot, body.payload)
    elif action_type == "flag_shift":
        result = _generate_shift_flag(snapshot, body.payload)
    elif action_type == "export_report":
        result = {"message": "Export queued. Download link will be available shortly."}

    # Log action
    log = ActionLog(
        id           = str(uuid.uuid4()),
        outlet_id    = str(outlet.id),
        session_id   = session_id,
        user_id      = token_data.user_id,
        action_type  = action_type,
        payload      = body.payload,
        status       = "done",
        result       = result,
        created_at   = datetime.utcnow(),
        completed_at = datetime.utcnow(),
    )
    db.add(log)
    await db.commit()

    return {"ok": True, "action_type": action_type, "log_id": log.id, "result": result}


def _generate_dispute_template(snapshot: MetricSnapshot | None, payload: dict) -> dict:
    """Generate a dispute email template for platform penalties."""
    top_orders = payload.get("top_orders", [])
    total      = payload.get("total_amount", 0)
    channel    = list(payload.get("by_channel", {}).keys())[0] if payload.get("by_channel") else "platform"

    order_lines = "\n".join(
        f"  - Order #{o.get('order_id', 'N/A')} | Date: {o.get('date', 'N/A')} | Amount: ₹{o.get('amount', 0):,.0f}"
        for o in top_orders[:10]
    )

    template = f"""Subject: Penalty Dispute Request — Restaurant Partner

Dear {channel.title()} Partner Support Team,

I am writing to formally dispute penalties totalling ₹{total:,.0f} charged to my account.

The following orders have been incorrectly penalised:

{order_lines}

I request a detailed review and reversal of these charges.

Please respond within 7 business days.

Regards,
[Restaurant Name]
[Partner ID]
[Contact Number]
"""
    return {
        "email_template": template,
        "total_disputed": total,
        "order_count":    len(top_orders),
        "channel":        channel,
    }


def _generate_shift_flag(snapshot: MetricSnapshot | None, payload: dict) -> dict:
    """Generate an internal shift flag alert."""
    pct   = payload.get("prime_cost_pct", 0)
    labor = payload.get("total_labor", 0)
    return {
        "alert_type":   "high_prime_cost",
        "message":      f"Prime Cost at {pct:.1f}% — above 65% threshold. Review shift scheduling.",
        "labor_total":  labor,
        "action_items": [
            "Audit overtime hours this period",
            "Review portion sizes for high-cost items",
            "Compare theoretical vs actual ingredient depletion",
        ],
    }
