"""
registry.py — Vertical plugin registry.
Add new verticals here. One line per vertical.
"""
from app.verticals.restaurant.metrics import RestaurantVertical
from app.verticals.base import BaseVertical

_REGISTRY = {
    "restaurant": RestaurantVertical(),
    # "clothing":  ClothingVertical(),   ← add when ready
    # "generic":   GenericVertical(),
}

def get_vertical(vertical_id: str) -> BaseVertical:
    v = _REGISTRY.get(vertical_id)
    if not v:
        raise ValueError(f"Unknown vertical: {vertical_id}. Available: {list(_REGISTRY.keys())}")
    return v

def list_verticals():
    return list(_REGISTRY.keys())
