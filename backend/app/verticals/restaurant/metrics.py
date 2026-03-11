"""
restaurant/metrics.py — All 8 F&B metrics with explicit sufficiency contracts.

Each metric:
1. Checks which sources are present in MetricFrames
2. Sets MetricSufficiency (COMPLETE / ESTIMATED / LOCKED / MANUAL)
3. Computes the metric using available data
4. Returns typed result with sufficiency tagged

Metrics:
  1. True Net Yield
  2. Dynamic Prime Cost %
  3. Penalty Leakage
  4. Inventory Variance %
  5. RevPASH
  6. True CAC
  7. AOV by Channel
  8. Revenue Dependency %
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel
import pandas as pd
import numpy as np

from app.verticals.base import BaseVertical, MetricResult, MetricSufficiency, Insight, Action
from app.ingestion.merger import MetricFrames

logger = logging.getLogger(__name__)


# ── Result models ─────────────────────────────────────────────────────────────

class NetYield(BaseModel):
    gross_sales:        Optional[float]
    total_commission:   Optional[float]
    total_ad_spend:     Optional[float]
    total_discounts:    Optional[float]
    total_penalties:    Optional[float]
    true_net_yield:     Optional[float]
    net_margin_pct:     Optional[float]
    used_actual_payout: bool = False   # True if payout file present, False if % fallback


class PrimeCost(BaseModel):
    total_cogs:         Optional[float]
    total_labor:        Optional[float]
    prime_cost:         Optional[float]
    prime_cost_pct:     Optional[float]
    status:             str = "unknown"   # green | amber | red
    cogs_source:        str = "none"      # tally | manual | none
    labor_source:       str = "none"      # payroll | manual | none


class PenaltyLeakage(BaseModel):
    total_leakage:  Optional[float]
    order_count:    int = 0
    by_channel:     Dict[str, float] = {}
    top_orders:     List[Dict] = []


class InventoryVariance(BaseModel):
    theoretical_cost:   Optional[float]
    actual_depletion:   Optional[float]
    variance_abs:       Optional[float]
    variance_pct:       Optional[float]
    status:             str = "ok"     # ok | moderate | high
    item_breakdown:     List[Dict] = []


class RevPASH(BaseModel):
    dine_in_revenue:    Optional[float]
    seats:              int = 0
    operating_hours:    float = 0.0
    days_in_period:     int = 0
    total_seat_hours:   Optional[float]
    revpash:            Optional[float]
    hourly_breakdown:   List[Dict] = []


class CACResult(BaseModel):
    ad_spend:       Optional[float]
    discounts:      Optional[float]
    new_customers:  int = 0
    cac:            Optional[float]
    is_estimated:   bool = True    # True until 3+ months of history exists


class ChannelMetric(BaseModel):
    channel:    str
    revenue:    float
    orders:     int
    aov:        float
    share_pct:  float


class RestaurantMetricResult(MetricResult):
    vertical: str = "restaurant"

    net_yield:          Optional[NetYield]       = None
    prime_cost:         Optional[PrimeCost]      = None
    penalty_leakage:    Optional[PenaltyLeakage] = None
    inventory_variance: Optional[InventoryVariance] = None
    revpash:            Optional[RevPASH]        = None
    cac_swiggy:         Optional[CACResult]      = None
    cac_zomato:         Optional[CACResult]      = None
    aov_by_channel:     List[ChannelMetric]      = []
    channel_dependency: Dict[str, float]         = {}
    insights:           List[Dict]               = []
    available_actions:  List[Dict]               = []

    class Config:
        arbitrary_types_allowed = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _s(v) -> Optional[float]:
    try:
        f = float(v)
        return None if (pd.isna(f) or np.isinf(f)) else round(f, 2)
    except Exception:
        return None

def _pct(num, den) -> Optional[float]:
    if not den or den == 0: return None
    return round(num / den * 100, 2)


# ── 1. True Net Yield ─────────────────────────────────────────────────────────

def compute_net_yield(
    frames: MetricFrames,
    config: dict,
    result: RestaurantMetricResult,
) -> NetYield:
    rev = frames.revenue_df
    if rev.empty:
        result.set_sufficiency("net_yield", MetricSufficiency.LOCKED)
        return NetYield(gross_sales=None, total_commission=None, total_ad_spend=None,
                        total_discounts=None, total_penalties=None, true_net_yield=None,
                        net_margin_pct=None)

    gross = float(rev["gross_amount"].fillna(0).sum())

    # Commission — actual from payout files or % fallback
    has_aggregator = frames.has_any("swiggy", "zomato")
    commission_in_data = rev["commission"].notna().any() and float(rev["commission"].fillna(0).sum()) > 0

    if commission_in_data:
        total_commission = float(rev["commission"].fillna(0).sum())
        used_actual = True
        suff = MetricSufficiency.COMPLETE
    elif has_aggregator:
        # Apply % to channel-specific revenue
        swiggy_rev = float(rev[rev["channel"] == "swiggy"]["gross_amount"].fillna(0).sum())
        zomato_rev = float(rev[rev["channel"] == "zomato"]["gross_amount"].fillna(0).sum())
        total_commission = (swiggy_rev * config.get("swiggy_commission_pct", 22.0) / 100 +
                            zomato_rev * config.get("zomato_commission_pct", 25.0) / 100)
        used_actual = False
        suff = MetricSufficiency.ESTIMATED
    else:
        total_commission = 0.0
        used_actual = False
        suff = MetricSufficiency.ESTIMATED

    ad_spend   = float(rev["ad_spend"].fillna(0).sum())
    discounts  = float(rev["discount"].fillna(0).sum())
    penalties  = float(rev["penalty"].fillna(0).sum())
    net_yield  = gross - total_commission - ad_spend - discounts - penalties

    result.set_sufficiency("net_yield", suff)
    return NetYield(
        gross_sales        = _s(gross),
        total_commission   = _s(total_commission),
        total_ad_spend     = _s(ad_spend),
        total_discounts    = _s(discounts),
        total_penalties    = _s(penalties),
        true_net_yield     = _s(net_yield),
        net_margin_pct     = _pct(net_yield, gross),
        used_actual_payout = used_actual,
    )


# ── 2. Dynamic Prime Cost ─────────────────────────────────────────────────────

def compute_prime_cost(
    frames: MetricFrames,
    config: dict,
    result: RestaurantMetricResult,
) -> PrimeCost:
    rev = frames.revenue_df
    gross = float(rev["gross_amount"].fillna(0).sum()) if not rev.empty else 0.0

    if gross == 0:
        result.set_sufficiency("prime_cost", MetricSufficiency.LOCKED)
        return PrimeCost(prime_cost_pct=None, status="unknown",
                         cogs_source="none", labor_source="none",
                         total_cogs=None, total_labor=None, prime_cost=None)

    # COGS
    if not frames.purchase_df.empty:
        total_cogs  = float(frames.purchase_df["total_cost"].fillna(0).sum())
        cogs_source = "tally"
    elif config.get("manual_cogs", 0) > 0:
        total_cogs  = float(config["manual_cogs"])
        cogs_source = "manual"
    else:
        total_cogs  = None
        cogs_source = "none"

    # Labor
    if not frames.labor_df.empty:
        total_labor  = float(frames.labor_df["labor_cost"].fillna(0).sum())
        labor_source = "payroll"
    elif config.get("manual_labor", 0) > 0:
        total_labor  = float(config["manual_labor"])
        labor_source = "manual"
    else:
        total_labor  = None
        labor_source = "none"

    # Sufficiency
    if total_cogs is not None and total_labor is not None:
        suff = MetricSufficiency.COMPLETE if (cogs_source != "manual" and labor_source != "manual") \
               else MetricSufficiency.MANUAL
    elif total_cogs is not None or total_labor is not None:
        suff = MetricSufficiency.ESTIMATED
    else:
        result.set_sufficiency("prime_cost", MetricSufficiency.LOCKED)
        return PrimeCost(prime_cost_pct=None, status="unknown",
                         cogs_source="none", labor_source="none",
                         total_cogs=None, total_labor=None, prime_cost=None)

    prime = (total_cogs or 0) + (total_labor or 0)
    pct   = _pct(prime, gross)
    status = "green" if pct and pct < 60 else "amber" if pct and pct < 65 else "red"

    result.set_sufficiency("prime_cost", suff)
    return PrimeCost(
        total_cogs   = _s(total_cogs),
        total_labor  = _s(total_labor),
        prime_cost   = _s(prime),
        prime_cost_pct = pct,
        status       = status,
        cogs_source  = cogs_source,
        labor_source = labor_source,
    )


# ── 3. Penalty Leakage ────────────────────────────────────────────────────────

def compute_penalty_leakage(
    frames: MetricFrames,
    result: RestaurantMetricResult,
) -> PenaltyLeakage:
    rev = frames.revenue_df
    if rev.empty or not rev["penalty"].notna().any():
        result.set_sufficiency("penalty_leakage", MetricSufficiency.LOCKED)
        return PenaltyLeakage(total_leakage=None)

    penalty_rows = rev[rev["penalty"].notna() & (rev["penalty"] > 0)].copy()
    total = float(penalty_rows["penalty"].sum())

    by_channel = {
        ch: round(float(grp["penalty"].sum()), 2)
        for ch, grp in penalty_rows.groupby("channel")
    }

    top_orders = []
    if penalty_rows["order_id"].notna().any():
        top = penalty_rows.sort_values("penalty", ascending=False).head(20)
        for _, r in top.iterrows():
            top_orders.append({
                "order_id": str(r.get("order_id", ""))[:30],
                "channel":  str(r.get("channel", "")),
                "amount":   round(float(r["penalty"]), 2),
                "date":     str(r["date"].date()) if pd.notna(r.get("date")) else "",
            })

    result.set_sufficiency("penalty_leakage", MetricSufficiency.COMPLETE)
    return PenaltyLeakage(
        total_leakage = _s(total),
        order_count   = len(penalty_rows),
        by_channel    = by_channel,
        top_orders    = top_orders,
    )


# ── 4. Inventory Variance ─────────────────────────────────────────────────────

def compute_inventory_variance(
    frames:     MetricFrames,
    config:     dict,
    result:     RestaurantMetricResult,
) -> InventoryVariance:
    item_df = frames.item_sales_df

    # Need item master for theoretical cost
    item_master: Dict[str, float] = config.get("item_master", {})

    if item_df.empty or not item_df["item_name"].notna().any():
        result.set_sufficiency("inventory_variance", MetricSufficiency.LOCKED)
        return InventoryVariance(theoretical_cost=None, actual_depletion=None,
                                  variance_abs=None, variance_pct=None, status="ok")

    # Theoretical depletion
    item_grp = item_df.groupby("item_name").agg(qty=("quantity", "sum")).reset_index()
    item_grp["unit_cost"] = item_grp["item_name"].map(item_master)
    item_grp = item_grp[item_grp["unit_cost"].notna()]

    if item_grp.empty:
        result.set_sufficiency("inventory_variance", MetricSufficiency.ESTIMATED)
        return InventoryVariance(theoretical_cost=None, actual_depletion=None,
                                  variance_abs=None, variance_pct=None,
                                  status="ok", item_breakdown=[])

    item_grp["theoretical_cost"] = item_grp["qty"] * item_grp["unit_cost"]
    theoretical = float(item_grp["theoretical_cost"].sum())

    # Actual depletion from stock entry
    stock: dict = config.get("stock_entry", {})
    actual = (stock.get("opening_stock_value", 0) +
              stock.get("purchases_value", 0) -
              stock.get("closing_stock_value", 0))

    variance_abs = actual - theoretical
    variance_pct = _pct(variance_abs, theoretical)
    status = ("high" if variance_pct and abs(variance_pct) > 10
              else "moderate" if variance_pct and abs(variance_pct) > 5
              else "ok")

    breakdown = item_grp.sort_values("theoretical_cost", ascending=False).head(10).to_dict("records")

    suff = MetricSufficiency.COMPLETE if stock.get("opening_stock_value") else MetricSufficiency.ESTIMATED
    result.set_sufficiency("inventory_variance", suff)

    return InventoryVariance(
        theoretical_cost = _s(theoretical),
        actual_depletion = _s(actual),
        variance_abs     = _s(variance_abs),
        variance_pct     = variance_pct,
        status           = status,
        item_breakdown   = breakdown,
    )


# ── 5. RevPASH ────────────────────────────────────────────────────────────────

def compute_revpash(
    frames: MetricFrames,
    config: dict,
    result: RestaurantMetricResult,
) -> RevPASH:
    seats          = config.get("seats", 0)
    opening_hours  = config.get("opening_hours", 0.0)

    rev = frames.revenue_df
    dine_df = rev[rev["channel"] == "dine_in"] if not rev.empty else pd.DataFrame()
    dine_revenue = float(dine_df["gross_amount"].fillna(0).sum()) if not dine_df.empty else 0.0

    if not seats or not opening_hours:
        result.set_sufficiency("revpash", MetricSufficiency.LOCKED)
        return RevPASH(dine_in_revenue=_s(dine_revenue), seats=seats,
                       operating_hours=opening_hours, days_in_period=0,
                       total_seat_hours=None, revpash=None)

    # Days in period — use actual date range
    if frames.date_from and frames.date_to:
        days = max(1, (frames.date_to - frames.date_from).days + 1)
    else:
        days = 1

    total_seat_hours = seats * opening_hours * days
    revpash_val      = dine_revenue / total_seat_hours if total_seat_hours else None

    # Hourly breakdown from timestamps if available
    hourly = []
    if not dine_df.empty and dine_df["date"].notna().any():
        dine_copy = dine_df.copy()
        dine_copy["hour"] = pd.to_datetime(dine_copy["date"]).dt.hour
        valid = dine_copy[dine_copy["hour"].notna()]
        if not valid.empty:
            hr_grp = valid.groupby("hour")["gross_amount"].sum().reset_index()
            hourly = [{"hour": int(r["hour"]), "value": round(float(r["gross_amount"]), 2)}
                      for _, r in hr_grp.iterrows()]

    result.set_sufficiency("revpash", MetricSufficiency.COMPLETE)
    return RevPASH(
        dine_in_revenue = _s(dine_revenue),
        seats           = seats,
        operating_hours = opening_hours,
        days_in_period  = days,
        total_seat_hours= _s(total_seat_hours),
        revpash         = _s(revpash_val),
        hourly_breakdown= hourly,
    )


# ── 6. True CAC ───────────────────────────────────────────────────────────────

def compute_cac(
    frames:  MetricFrames,
    channel: str,
    config:  dict,
    result:  RestaurantMetricResult,
    months_of_history: int = 1,
) -> Optional[CACResult]:
    rev = frames.revenue_df
    if rev.empty: return None

    ch_df = rev[rev["channel"] == channel]
    if ch_df.empty: return None

    ad_spend  = float(ch_df["ad_spend"].fillna(0).sum())
    discounts = float(ch_df["discount"].fillna(0).sum())
    total_spend = ad_spend + discounts

    # New customer count — longitudinal if possible
    new_customers = 0
    if ch_df["customer_id"].notna().any():
        unique_cids = ch_df[ch_df["customer_id"].notna() & (ch_df["customer_id"] != "")]["customer_id"]
        # Without prior history, all unique customers in window are treated as new (overestimate)
        new_customers = int(unique_cids.nunique())
    else:
        new_customers = max(1, len(ch_df))

    cac = _s(total_spend / new_customers) if new_customers > 0 else None
    # Flag as estimated if < 3 months of history
    is_estimated = months_of_history < 3

    metric_key = f"cac_{channel}"
    result.set_sufficiency(
        metric_key,
        MetricSufficiency.ESTIMATED if is_estimated else MetricSufficiency.COMPLETE
    )
    return CACResult(
        ad_spend      = _s(ad_spend),
        discounts     = _s(discounts),
        new_customers = new_customers,
        cac           = cac,
        is_estimated  = is_estimated,
    )


# ── 7 & 8. AOV by Channel + Revenue Dependency ───────────────────────────────

def compute_channel_metrics(
    frames: MetricFrames,
    result: RestaurantMetricResult,
):
    rev = frames.revenue_df
    if rev.empty:
        result.set_sufficiency("aov_by_channel", MetricSufficiency.LOCKED)
        result.set_sufficiency("channel_dependency", MetricSufficiency.LOCKED)
        return [], {}

    total = float(rev["gross_amount"].fillna(0).sum())
    channels = []

    for ch in rev["channel"].unique():
        ch_df = rev[rev["channel"] == ch]
        revenue = float(ch_df["gross_amount"].fillna(0).sum())
        orders  = len(ch_df)
        aov     = revenue / orders if orders else 0
        channels.append(ChannelMetric(
            channel   = ch,
            revenue   = round(revenue, 2),
            orders    = orders,
            aov       = round(aov, 2),
            share_pct = round(_pct(revenue, total) or 0, 2),
        ))

    channels.sort(key=lambda x: x.revenue, reverse=True)
    dependency = {c.channel: c.share_pct for c in channels}

    result.set_sufficiency("aov_by_channel",     MetricSufficiency.COMPLETE)
    result.set_sufficiency("channel_dependency", MetricSufficiency.COMPLETE)
    return channels, dependency


# ── Main vertical class ───────────────────────────────────────────────────────

class RestaurantVertical(BaseVertical):
    vertical_id = "restaurant"

    def compute_metrics(self, frames: MetricFrames, config: dict) -> RestaurantMetricResult:
        from datetime import datetime as dt

        result = RestaurantMetricResult(
            vertical      = "restaurant",
            computed_at   = dt.utcnow().isoformat(),
            date_from     = str(frames.date_from.date()) if frames.date_from else None,
            date_to       = str(frames.date_to.date())   if frames.date_to   else None,
            sources_used  = frames.sources_present,
            alignment_warnings = frames.alignment_warnings,
        )

        result.net_yield          = compute_net_yield(frames, config, result)
        result.prime_cost         = compute_prime_cost(frames, config, result)
        result.penalty_leakage    = compute_penalty_leakage(frames, result)
        result.inventory_variance = compute_inventory_variance(frames, config, result)
        result.revpash            = compute_revpash(frames, config, result)
        result.cac_swiggy         = compute_cac(frames, "swiggy", config, result)
        result.cac_zomato         = compute_cac(frames, "zomato", config, result)

        channels, dependency      = compute_channel_metrics(frames, result)
        result.aov_by_channel     = channels
        result.channel_dependency = dependency

        from app.verticals.restaurant.insights import generate_insights
        from app.verticals.restaurant.actions  import get_available_actions
        result.insights          = [i.__dict__ for i in generate_insights(result)]
        result.available_actions = [a.__dict__ for a in get_available_actions(result)]

        return result

    def generate_insights(self, result): return []
    def get_available_actions(self, result): return []
    def get_required_sources(self): return ["swiggy", "zomato", "petpooja", "tally", "payroll"]
