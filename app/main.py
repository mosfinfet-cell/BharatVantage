"""
main.py — FastAPI application entry point.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import create_tables
from app.core.logging import configure_logging, bind_request_context, clear_request_context, get_logger

from app.api.v1.auth    import router as auth_router
from app.api.v1.upload  import router as upload_router
from app.api.v1.config  import router as config_router
from app.api.v1.actions import router as actions_router
from app.api.v1.compute import (
    compute_router, status_router, metrics_router
)

# Configure structured logging before anything else logs
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_tables()
    logger.info("BharatVantage started", version="3.0.0", debug=settings.DEBUG)
    yield
    # Shutdown
    logger.info("BharatVantage shutting down")


app = FastAPI(
    title       = settings.APP_NAME,
    version     = "3.0.0",
    description = "Multi-vertical restaurant analytics platform",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


@app.middleware("http")
async def log_request_context(request: Request, call_next):
    """
    Bind outlet_id and request path to structlog context for every request.
    This means outlet_id appears automatically on every log line within
    a request without having to pass it through every function call.
    """
    outlet_id = request.headers.get("X-Outlet-ID", "")
    bind_request_context(
        outlet_id = outlet_id,
        path      = request.url.path,
        method    = request.method,
    )
    try:
        response = await call_next(request)
        return response
    finally:
        clear_request_context()

# ── Routes ─────────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"

app.include_router(auth_router,    prefix=f"{PREFIX}/auth",    tags=["Auth"])
app.include_router(upload_router,  prefix=PREFIX,              tags=["Upload"])
app.include_router(config_router,  prefix=PREFIX,              tags=["Config"])
app.include_router(actions_router, prefix=PREFIX,              tags=["Actions"])
app.include_router(compute_router, prefix=PREFIX,              tags=["Compute"])
app.include_router(status_router,  prefix=PREFIX,              tags=["Status"])
app.include_router(metrics_router, prefix=PREFIX,              tags=["Metrics"])


# ── Health checks ──────────────────────────────────────────────────────────────

@app.get("/health/live", tags=["Health"])
async def liveness():
    """Railway uses this to decide whether to restart the process."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
async def readiness():
    """Railway uses this to decide whether to route traffic here."""
    from app.core.database import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    if not db_ok:
        from fastapi import Response
        return Response(status_code=503, content='{"db": "unreachable"}')
    return {"db": "ok"}


@app.get("/", tags=["Root"])
async def root():
    return {"app": settings.APP_NAME, "version": "3.0.0", "docs": "/docs"}
