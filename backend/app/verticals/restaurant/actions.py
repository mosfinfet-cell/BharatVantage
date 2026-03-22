"""
restaurant/actions.py — Executable actions from metric state.

get_available_actions lives in insights.py (same file, written together).
This module re-exports it so metrics.py can import from either location
without breaking the separation of concerns expected by the import path.
"""
from app.verticals.restaurant.insights import get_available_actions  # noqa: F401
