"""
worker.py — ARQ worker entry point.
Run as separate Railway service: arq app.worker.WorkerSettings
"""
from app.core.jobs import WorkerSettings  # noqa: F401 — imported for ARQ discovery
