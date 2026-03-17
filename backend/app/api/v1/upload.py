"""
upload.py — POST /api/v1/upload
Accepts multiple files, validates, hashes, uploads to R2, creates session.
Returns session_id and per-file detection results immediately.
Ingestion runs asynchronously via ARQ job.
"""
import hashlib
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.core.auth import get_current_outlet, TokenData, get_current_user
from app.core.storage import storage
from app.core.rate_limit import check_upload_rate_limit
from app.ingestion.sanitiser import sanitise, validate_file
from app.ingestion.fingerprint import detect_source
from app.models.ingestion import UploadSession, SourceFile
from app.models.org import Outlet


router = APIRouter()

MAX_FILE_BYTES    = settings.MAX_FILE_SIZE_MB * 1024 * 1024
MAX_SESSION_BYTES = settings.MAX_SESSION_SIZE_MB * 1024 * 1024

# Valid source types the user can override to
VALID_SOURCE_TYPES = {"swiggy", "zomato", "petpooja", "tally", "payroll", "generic"}


class FileDetectionResult(BaseModel):
    file_id:        str
    filename:       str
    row_count:      int
    detected_source:str
    data_category:  str
    confidence:     float
    format_version: str
    needs_confirm:  bool
    headers:        List[str]
    warnings:       List[str]


class UploadSessionResponse(BaseModel):
    session_id:     str
    outlet_id:      str
    files:          List[FileDetectionResult]
    needs_confirm:  bool
    total_rows:     int


@router.post("/upload", response_model=UploadSessionResponse)
async def upload_files(
    files:      List[UploadFile] = File(...),
    outlet:     Outlet           = Depends(get_current_outlet),
    db:         AsyncSession     = Depends(get_db),
):
    if not files:
        raise HTTPException(400, "No files provided.")
    if len(files) > 10:
        raise HTTPException(400, "Maximum 10 files per upload session.")

    # Enforce per-org rate limit before touching R2 or the DB
    await check_upload_rate_limit(outlet.org_id)

    session_id = str(uuid.uuid4())
    session    = UploadSession(
        id             = session_id,
        outlet_id      = str(outlet.id),
        vertical       = "restaurant",  # industry from org.industry -- skipped to avoid lazy load
        ingest_status  = "pending",
        compute_status = "idle",
        created_at     = datetime.utcnow(),
    )
    db.add(session)
    await db.flush()

    results:      List[FileDetectionResult] = []
    total_size    = 0
    needs_confirm = False

    for upload in files:
        content = await upload.read()
        total_size += len(content)

        # Size checks
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(413, f"{upload.filename} exceeds {settings.MAX_FILE_SIZE_MB}MB limit.")
        if total_size > MAX_SESSION_BYTES:
            raise HTTPException(413, f"Total upload exceeds {settings.MAX_SESSION_SIZE_MB}MB limit.")

        # Validate file content (magic bytes / encoding)
        is_valid, err_msg = validate_file(content, upload.filename)
        if not is_valid:
            raise HTTPException(422, f"{upload.filename}: {err_msg}")

        # Content hash for deduplication
        content_hash = hashlib.sha256(content).hexdigest()

        # Check if this exact file was already uploaded for this outlet
        existing = await db.execute(
            select(SourceFile).where(
                SourceFile.content_hash == content_hash,
                SourceFile.parse_status == "done",
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, f"{upload.filename} was already uploaded (identical content).")

        # Sanitise and detect
        try:
            df, headers = sanitise(content, upload.filename)
        except ValueError as e:
            raise HTTPException(422, f"{upload.filename}: {e}")

        detection = detect_source(headers, df)

        # Determine storage filename
        ext         = upload.filename.rsplit(".", 1)[-1].lower()
        file_id     = str(uuid.uuid4())
        storage_key = await storage.upload(
            content     = content,
            session_id  = session_id,
            filename    = f"{file_id}.{ext}",
            content_type= storage.get_content_type(upload.filename),
        )

        sf = SourceFile(
            id               = file_id,
            session_id       = session_id,
            filename         = f"{file_id}.{ext}",
            original_name    = upload.filename,
            file_size        = len(content),
            content_hash     = content_hash,
            storage_key      = storage_key,
            detected_source  = detection.source_type,
            format_version   = detection.format_version,
            confidence       = detection.confidence,
            confirmed_source = detection.source_type,
            data_category    = detection.data_category,
            row_count        = len(df),
            parse_status     = "pending",
            created_at       = datetime.utcnow(),
        )
        db.add(sf)

        if detection.needs_confirm:
            needs_confirm = True

        results.append(FileDetectionResult(
            file_id         = file_id,
            filename        = upload.filename,
            row_count       = len(df),
            detected_source = detection.source_type,
            data_category   = detection.data_category,
            confidence      = round(detection.confidence, 2),
            format_version  = detection.format_version,
            needs_confirm   = detection.needs_confirm,
            headers         = headers[:20],
            warnings        = (["Unknown format version — verify column mapping"]
                               if detection.format_version == "unknown" else []),
        ))

    await db.commit()

    return UploadSessionResponse(
        session_id    = session_id,
        outlet_id     = str(outlet.id),
        files         = results,
        needs_confirm = needs_confirm,
        total_rows    = sum(r.row_count for r in results),
    )


# ── Confirm endpoint ──────────────────────────────────────────────────────────

class FileConfirmation(BaseModel):
    file_id:          str
    confirmed_source: str   # must be in VALID_SOURCE_TYPES


class ConfirmRequest(BaseModel):
    confirmations: list[FileConfirmation]


class ConfirmResponse(BaseModel):
    session_id: str
    confirmed:  list[dict]   # [{file_id, confirmed_source, data_category}]
    ready_to_compute: bool   # True when all files are confirmed


# Map source_type → data_category so the pipeline routes records correctly.
# This mirrors the same mapping in fingerprint.py.
_SOURCE_TO_CATEGORY = {
    "swiggy":   "sales_aggregator",
    "zomato":   "sales_aggregator",
    "petpooja": "sales_pos",
    "tally":    "purchases",
    "payroll":  "labor",
    "generic":  "generic",
}


@router.patch("/upload/{session_id}/confirm", response_model=ConfirmResponse)
async def confirm_sources(
    session_id: str,
    body:       ConfirmRequest,
    outlet:     Outlet       = Depends(get_current_outlet),
    db:         AsyncSession = Depends(get_db),
):
    """
    Override auto-detected source types for files in a session.

    Called when upload returns needs_confirm: true (confidence < 0.70).
    Must be called before POST /compute/{session_id} — compute checks
    that all files have a confirmed_source before enqueueing the job.

    Only files belonging to the authenticated outlet's session can be
    confirmed — other file IDs in the request are silently ignored to
    avoid leaking existence of other orgs' data.
    """
    # Verify session belongs to this outlet
    sess_result = await db.execute(
        select(UploadSession).where(
            UploadSession.id        == session_id,
            UploadSession.outlet_id == str(outlet.id),
            UploadSession.deleted_at.is_(None),
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found.")

    if session.compute_status in ("queued", "running", "done"):
        raise HTTPException(
            400,
            f"Cannot confirm sources after compute has started "
            f"(current status: {session.compute_status})."
        )

    confirmed_results = []

    for conf in body.confirmations:
        if conf.confirmed_source not in VALID_SOURCE_TYPES:
            raise HTTPException(
                400,
                f"Invalid source type '{conf.confirmed_source}'. "
                f"Valid options: {sorted(VALID_SOURCE_TYPES)}"
            )

        # Load file — only from this session (enforces ownership)
        file_result = await db.execute(
            select(SourceFile).where(
                SourceFile.id         == conf.file_id,
                SourceFile.session_id == session_id,
            )
        )
        sf = file_result.scalar_one_or_none()
        if not sf:
            # Skip unknown file IDs — don't leak 404 for other orgs' files
            continue

        sf.confirmed_source = conf.confirmed_source
        sf.data_category    = _SOURCE_TO_CATEGORY[conf.confirmed_source]

        confirmed_results.append({
            "file_id":          sf.id,
            "original_name":    sf.original_name,
            "confirmed_source": sf.confirmed_source,
            "data_category":    sf.data_category,
        })

    await db.commit()

    # Check if all files in the session are now confirmed
    all_files_result = await db.execute(
        select(SourceFile).where(SourceFile.session_id == session_id)
    )
    all_files = all_files_result.scalars().all()
    ready     = all(f.confirmed_source is not None for f in all_files)

    return ConfirmResponse(
        session_id        = session_id,
        confirmed         = confirmed_results,
        ready_to_compute  = ready,
    )


@router.get("/upload/sessions")
async def list_sessions(
    outlet: Outlet       = Depends(get_current_outlet),
    db:     AsyncSession = Depends(get_db),
):
    """List all upload sessions for the current outlet, newest first."""
    from sqlalchemy import select, desc
    from app.models.ingestion import UploadSession
    result = await db.execute(
        select(UploadSession)
        .where(
            UploadSession.outlet_id == str(outlet.id),
            UploadSession.deleted_at.is_(None),
        )
        .order_by(desc(UploadSession.created_at))
        .limit(20)
    )
    sessions = result.scalars().all()
    return [
        {
            "id":             s.id,
            "ingest_status":  s.ingest_status,
            "compute_status": s.compute_status,
            "sources_present": list(s.source_coverage.keys()) if s.source_coverage else [],
            "date_from":      s.date_from.isoformat()  if s.date_from  else None,
            "date_to":        s.date_to.isoformat()    if s.date_to    else None,
            "created_at":     s.created_at.isoformat() if s.created_at else None,
            "error_message":  s.error_message,
        }
        for s in sessions
    ]
