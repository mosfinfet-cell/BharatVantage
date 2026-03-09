"""
base.py — Abstract vertical interface and MetricSufficiency contract.

Every vertical (restaurant, generic, clothing...) implements BaseVertical.
This ensures the API layer and job runner work with any vertical
without knowing its internals.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class MetricSufficiency(str, Enum):
    """
    Data quality status for each computed metric.
    Drives the UI state — full value, estimated value, or locked card.
    """
    COMPLETE  = "complete"    # all required sources present, full accuracy
    ESTIMATED = "estimated"   # some sources missing, fallback % used
    LOCKED    = "locked"      # insufficient data — cannot compute
    MANUAL    = "manual"      # computed from manual entry, not file data


@dataclass
class Insight:
    type:     str              # good | warn | info
    icon:     str
    priority: int              # 1 = highest
    title:    str
    body:     str
    action:   Optional[str] = None   # action_type if actionable


@dataclass
class Action:
    action_type: str           # raise_dispute | flag_shift | export_report
    label:       str           # display label
    payload:     Dict          # data needed to execute the action
    metric_ref:  str           # which metric triggered this action


class MetricResult(BaseModel):
    """
    Base metric result. Each vertical extends this with its own fields.
    Includes a sufficiency_map for every metric.
    """
    vertical:    str
    computed_at: str
    date_from:   Optional[str] = None
    date_to:     Optional[str] = None
    sources_used: List[str] = []
    alignment_warnings: List[str] = []

    # Per-metric sufficiency — populated by compute_metrics
    _sufficiency: Dict[str, MetricSufficiency] = {}

    def sufficiency_map(self) -> Dict[str, str]:
        return {k: v.value for k, v in self._sufficiency.items()}

    def set_sufficiency(self, metric: str, status: MetricSufficiency):
        self._sufficiency[metric] = status

    class Config:
        arbitrary_types_allowed = True


class BaseVertical(ABC):
    """
    Abstract vertical plugin. Implement this for each industry module.
    """
    vertical_id: str = "base"

    @abstractmethod
    def compute_metrics(
        self,
        frames: Any,    # MetricFrames from merger
        config: dict,
    ) -> MetricResult:
        """Run all metric calculations. Return populated MetricResult."""
        pass

    @abstractmethod
    def generate_insights(self, result: MetricResult) -> List[Insight]:
        """Generate smart insight cards from computed metrics."""
        pass

    @abstractmethod
    def get_available_actions(self, result: MetricResult) -> List[Action]:
        """Return list of executable actions based on current metric state."""
        pass

    @abstractmethod
    def get_required_sources(self) -> List[str]:
        """Return list of source types this vertical can use."""
        pass

    def describe_sufficiency(self, metric: str, result: MetricResult) -> MetricSufficiency:
        return result._sufficiency.get(metric, MetricSufficiency.LOCKED)
