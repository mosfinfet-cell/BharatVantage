"""
engine.py — BharatVantage v1.1 Metric Computation Engine.

Computes the full MetricSnapshot.result JSON for all outlet types.
Called by run_compute_job in jobs.py.

Architecture:
  compute_metrics(frames, config) → MetricResult
  MetricResult.model_dump()       → stored in metric_snapshots.result
  MetricResult.sufficiency_map()  → stored in metric_snapshots.sufficiency

Outlet types:
  dine_in       → compute_dine_in_metrics()
  hybrid        → compute_hybrid_metrics() (calls both dine-in + online branches)
  cloud_kitchen → compute_cloud_kitchen_metrics()
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Optional

import pandas as pd
import numpy as np


# ── Config passed from jobs.py ─────────────────────────────────────────────────

@dataclass
class OutletConfig:
    outlet_id:               str
    outlet_type:             str          # dine_in | hybrid | cloud_kitchen
    seat_count:              int  = 40
    opening_hours_per_day:   float = 12.0
    gst_rate_pct:            float = 5.0

    # Packaging cost tiers (v1.1)
    pkg_tier1:              float = 12.0  # orders < ₹150
    pkg_tier2:              float = 20.0  # orders ₹150–₹400
    pkg_tier3:              float = 35.0  # orders > ₹400
    pkg_configured:         bool  = False

    # Fixed costs (cloud kitchen break-even)
    monthly_rent:           float = 0.0
    monthly_utilities:      float = 0.0

    # Settlement cycles
    settlement_cycle_swiggy: int = 7
    settlement_cycle_zomato: int = 7

    # Food cost fallback rates (when Tally absent)
    food_cost_fallback_pct_dinein:  float = 0.32
    food_cost_fallback_pct_online:  float = 0.32


# ── Metric frames from merger.py ──────────────────────────────────────────────

@dataclass
class MetricFrames:
    """DataFrames built from stored records for a session's date range."""
    sales:     pd.DataFrame = field(default_factory=pd.DataFrame)
    purchases: pd.DataFrame = field(default_factory=pd.DataFrame)
    labor:     pd.DataFrame = field(default_factory=pd.DataFrame)
    items:     pd.DataFrame = field(default_factory=pd.DataFrame)    # item_master
    manuals:   pd.DataFrame = field(default_factory=pd.DataFrame)    # manual_entries
    date_from: Optional[date] = None
    date_to:   Optional[date] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division with zero-denominator guard. Returns default if denominator is 0."""
    if denominator == 0 or math.isnan(denominator):
        return default
    return numerator / denominator


def _round2(val: float | None) -> float | None:
    """Round to 2 decimal places. Preserves None."""
    if val is None:
        return None
    return round(float(val), 2)


def _packaging_cost(order_value: float, config: OutletConfig) -> float:
    """
    v1.1: 3-tier packaging cost based on order value.
    Fallback to flat tier2 (₹20) if not operator-configured.
    """
    if order_value < 150:
        return config.pkg_tier1
    elif order_value <= 400:
        return config.pkg_tier2
    else:
        return config.pkg_tier3


def _gst_on_commission(commission: float) -> float:
    """18% GST on aggregator commission under reverse charge mechanism."""
    return round(commission * 0.18, 2)


def _service_period(hour: int) -> str:
    """Derive service period from hour of day."""
    if 11 <= hour < 16:
        return "lunch"
    elif 18 <= hour < 23:
        return "dinner"
    return "all_day"


def _format_inr(value: float) -> str:
    """Format rupee value in Indian lakh notation for display."""
    if value >= 1_00_000:
        return f"₹{value / 1_00_000:.1f}L"
    elif value >= 1_000:
        return f"₹{value:,.0f}"
    return f"₹{value:.0f}"


# ── Sufficiency logic ─────────────────────────────────────────────────────────

def _has_sales(frames: MetricFrames, channel_filter: list[str] | None = None) -> bool:
    if frames.sales.empty:
        return False
    if channel_filter:
        return not frames.sales[frames.sales["channel"].isin(channel_filter)].empty
    return True


def _has_purchases(frames: MetricFrames) -> bool:
    return not frames.purchases.empty


def _has_labor(frames: MetricFrames) -> bool:
    return not frames.labor.empty


def _has_items(frames: MetricFrames) -> bool:
    return len(frames.items) >= 5  # locked until at least 5 items in master


def _has_manual_cash(frames: MetricFrames) -> bool:
    if frames.manuals.empty:
        return False
    return "cash_drawer" in frames.manuals["entry_type"].values


def _has_manual_rating(frames: MetricFrames, platform: str) -> bool:
    if frames.manuals.empty:
        return False
    r = frames.manuals[
        (frames.manuals["entry_type"] == "platform_rating") &
        (frames.manuals["platform"] == platform)
    ]
    return len(r) >= 2  # need at least 2 months for correlation


# ── DINE-IN METRICS ───────────────────────────────────────────────────────────

def compute_dine_in_block(frames: MetricFrames, config: OutletConfig) -> dict:
    """
    Computes all dine-in tab metrics (M1–M5 + People).
    Used by both TYPE A and the Dine-in Tab of TYPE B.
    """
    dinein_channels = ["dine_in", "takeaway"]
    df = frames.sales[
        frames.sales["channel"].isin(dinein_channels) &
        ~frames.sales["is_deduplicated"].fillna(False)
    ].copy() if not frames.sales.empty else pd.DataFrame()

    result: dict[str, Any] = {}

    # ── M1: Today's Earnings vs same weekday last week ────────────────────────
    today = date.today()
    last_week_same = today - timedelta(days=7)

    def _day_earnings(target_date: date) -> float:
        if df.empty or "date" not in df.columns:
            return 0.0
        mask = df["date"].dt.date == target_date
        return float(df[mask]["net_payout"].fillna(0).sum())

    result["today_earnings"]             = _round2(_day_earnings(today))
    result["today_prev_same_weekday"]    = _round2(_day_earnings(last_week_same))

    # ── M2: Cash Reconciliation ───────────────────────────────────────────────
    cash_block: dict[str, Any] = {
        "cash_pct": 0.0,
        "upi_pct":  0.0,
        "daily_gaps":            [],
        "manual_entry_required": True,
    }

    if not df.empty and "payment_method" in df.columns:
        total = df["gross_amount"].fillna(0).sum()
        if total > 0:
            cash_total = df[df["payment_method"] == "cash"]["gross_amount"].fillna(0).sum()
            upi_total  = df[df["payment_method"].isin(["upi","card"])]["gross_amount"].fillna(0).sum()
            cash_block["cash_pct"] = _round2(cash_total / total * 100)
            cash_block["upi_pct"]  = _round2(upi_total  / total * 100)

        # Daily gaps: petpooja expected vs manual actual
        if _has_manual_cash(frames):
            cash_block["manual_entry_required"] = False
            manual_cash = frames.manuals[frames.manuals["entry_type"] == "cash_drawer"]
            gaps = []
            for _, row in manual_cash.iterrows():
                entry_date = pd.to_datetime(row["entry_date"]).date()
                mask = df["date"].dt.date == entry_date
                expected = float(df[mask & (df["payment_method"] == "cash")]["gross_amount"].fillna(0).sum())
                actual   = float(row["value"])
                gap      = expected - actual
                if abs(gap) > 50:   # filter noise below ₹50
                    gaps.append({
                        "date":     entry_date.isoformat(),
                        "expected": _round2(expected),
                        "actual":   _round2(actual),
                        "gap":      _round2(gap),
                    })
            cash_block["daily_gaps"] = gaps

    result["cash_reconciliation"] = cash_block

    # ── M3: Average Bill per Table ────────────────────────────────────────────
    if not df.empty and "order_id" in df.columns:
        unique_orders = df.dropna(subset=["order_id"])
        if not unique_orders.empty:
            bill_per_order = unique_orders.groupby("order_id")["gross_amount"].sum()
            result["avg_bill_per_table"]      = _round2(float(bill_per_order.mean()))
            result["avg_bill_per_table_prev"] = None   # populated by prev-period comparison
        else:
            result["avg_bill_per_table"] = None
    else:
        result["avg_bill_per_table"] = None

    # ── M4: Table Turn Summary (per service period) ───────────────────────────
    table_turns: dict[str, float] = {}
    if not df.empty and config.seat_count > 0 and "date" in df.columns:
        if "service_period" not in df.columns:
            df["service_period"] = df["date"].dt.hour.apply(_service_period)
        for label, grp in df.groupby(["date", "service_period"]):
            day_label = f"{pd.to_datetime(label[0]).strftime('%A')} {label[1].title()}"
            orders = grp["order_id"].nunique() if "order_id" in grp.columns else 0
            turns  = _round2(orders / config.seat_count)
            table_turns[day_label] = turns

    result["table_turns"] = table_turns

    # ── M5: Best and Worst Service ────────────────────────────────────────────
    result["best_service"]  = None
    result["worst_service"] = None
    if not df.empty and "date" in df.columns:
        df["_day_service"] = (
            df["date"].dt.strftime("%A ") +
            df["date"].dt.hour.apply(_service_period).str.title()
        )
        service_rev = df.groupby("_day_service")["net_payout"].sum().fillna(0)
        if not service_rev.empty:
            result["best_service"]  = {"label": service_rev.idxmax(), "amount": _round2(float(service_rev.max()))}
            result["worst_service"] = {"label": service_rev.idxmin(), "amount": _round2(float(service_rev.min()))}

    # ── M6/M7: Staff Cost ─────────────────────────────────────────────────────
    staff_cost_total = float(frames.labor["labor_cost"].fillna(0).sum()) if not frames.labor.empty else 0.0
    net_rev_dinein   = float(df["net_payout"].fillna(0).sum()) if not df.empty else 0.0

    result["staff_cost_total"]  = _round2(staff_cost_total)
    result["staff_cost_pct"]    = _round2(_safe_div(staff_cost_total, net_rev_dinein) * 100)

    # Role breakdown
    role_breakdown = []
    if not frames.labor.empty and "role" in frames.labor.columns:
        for role, grp in frames.labor.groupby("role"):
            amt = float(grp["labor_cost"].fillna(0).sum())
            role_breakdown.append({
                "role":   role,
                "amount": _round2(amt),
                "pct":    _round2(_safe_div(amt, staff_cost_total) * 100),
            })
    result["staff_role_breakdown"] = sorted(role_breakdown, key=lambda x: -x["amount"])

    # Floor staff low days
    low_threshold = 8000.0
    low_days = 0
    if not df.empty and "date" in df.columns:
        daily_rev = df.groupby(df["date"].dt.date)["net_payout"].sum()
        low_days = int((daily_rev < low_threshold).sum())
    result["floor_staff_low_days"]      = low_days
    result["floor_staff_low_threshold"] = low_threshold

    # ── M8: Prime Cost ────────────────────────────────────────────────────────
    food_cost_total = float(frames.purchases["total_cost"].fillna(0).sum()) if not frames.purchases.empty else 0.0
    if food_cost_total == 0.0 and net_rev_dinein > 0:
        food_cost_total = net_rev_dinein * config.food_cost_fallback_pct_dinein

    prime_cost = food_cost_total + staff_cost_total
    prime_cost_pct = _safe_div(prime_cost, net_rev_dinein) * 100 if net_rev_dinein > 0 else None

    result["prime_cost_pct"] = _round2(prime_cost_pct)
    result["prime_cost_breakdown"] = {
        "food_cost":  _round2(food_cost_total),
        "staff_cost": _round2(staff_cost_total),
        "total":      _round2(prime_cost),
    }

    # ── RevPASH (earning per chair per hour) ──────────────────────────────────
    period_days = (frames.date_to - frames.date_from).days + 1 if frames.date_from and frames.date_to else 30
    total_seat_hours = config.seat_count * config.opening_hours_per_day * period_days
    result["revpash"] = _round2(_safe_div(net_rev_dinein, total_seat_hours))

    return result


# ── ONLINE METRICS ────────────────────────────────────────────────────────────

def compute_online_block(frames: MetricFrames, config: OutletConfig) -> dict:
    """
    Computes all online tab metrics (H-O1 through H-O7 / cloud kitchen variants).
    Covers: pending settlements, payout bridge, platform earnings,
            true order margin (per platform), penalties (3-state), ad spend,
            item channel margin.
    """
    online_channels = ["swiggy", "zomato"]
    df = frames.sales[
        frames.sales["channel"].isin(online_channels) &
        ~frames.sales["is_deduplicated"].fillna(False)
    ].copy() if not frames.sales.empty else pd.DataFrame()

    result: dict[str, Any] = {}

    # ── H-O1: Pending Settlements ─────────────────────────────────────────────
    pending = []
    today = date.today()
    for platform, cycle_days in [("swiggy", config.settlement_cycle_swiggy),
                                  ("zomato", config.settlement_cycle_zomato)]:
        if df.empty:
            continue
        plat_df = df[(df["source_type"] == platform) & (~df["settled"].fillna(False))]
        if plat_df.empty:
            continue
        amt = float(plat_df["net_payout"].fillna(0).sum())
        # Expected date: latest order date + settlement cycle
        max_date = plat_df["date"].max()
        if pd.notna(max_date):
            expected = (pd.to_datetime(max_date).date() + timedelta(days=cycle_days))
        else:
            expected = today + timedelta(days=cycle_days)
        pending.append({
            "platform":      platform,
            "amount":        _round2(amt),
            "expected_date": expected.isoformat(),
            "overdue":       expected < today,
        })

    result["pending_settlements"] = pending

    # ── H-O2: Payout Bridge (waterfall) ──────────────────────────────────────
    gross_total       = float(df["gross_amount"].fillna(0).sum()) if not df.empty else 0.0
    commission_total  = float(df["commission"].fillna(0).sum())   if not df.empty else 0.0
    gst_comm_total    = float(df["gst_on_commission"].fillna(0).sum()) if not df.empty else _gst_on_commission(commission_total)
    ad_spend_total    = float(df["ad_spend"].fillna(0).sum())     if not df.empty else 0.0
    discount_total    = float(df["discount"].fillna(0).sum())     if not df.empty else 0.0
    penalty_total     = float(df["penalty"].fillna(0).sum())      if not df.empty else 0.0
    actual_payout     = gross_total - commission_total - gst_comm_total - ad_spend_total - discount_total - penalty_total

    result["payout_bridge"] = {
        "gross_revenue":          _round2(gross_total),
        "less_commission":        _round2(-commission_total),
        "less_gst_on_commission": _round2(-gst_comm_total),
        "less_ad_spend":          _round2(-ad_spend_total),
        "less_discounts":         _round2(-discount_total),
        "less_penalties":         _round2(-penalty_total),
        "actual_payout":          _round2(actual_payout),
    }

    # ── H-O3: Platform Earnings (paisa framing) ───────────────────────────────
    platform_earnings: dict[str, dict] = {}
    for platform in ["swiggy", "zomato"]:
        if df.empty:
            continue
        pf = df[df["source_type"] == platform]
        if pf.empty:
            continue
        gross_p      = float(pf["gross_amount"].fillna(0).sum())
        comm_p       = float(pf["commission"].fillna(0).sum())
        gst_comm_p   = float(pf["gst_on_commission"].fillna(0).sum()) or _gst_on_commission(comm_p)
        ad_p         = float(pf["ad_spend"].fillna(0).sum())
        pen_p        = float(pf["penalty"].fillna(0).sum())
        disc_p       = float(pf["discount"].fillna(0).sum())
        kept_p       = gross_p - comm_p - gst_comm_p - ad_p - pen_p - disc_p
        cut_p        = comm_p + gst_comm_p + ad_p + pen_p + disc_p
        eff_pct_p    = _round2(_safe_div(cut_p, gross_p) * 100) if gross_p > 0 else 0.0
        paisa_p      = round(_safe_div(cut_p, gross_p) * 100) if gross_p > 0 else 0

        platform_earnings[platform] = {
            "gross":              _round2(gross_p),
            "commission":         _round2(comm_p),
            "gst_on_commission":  _round2(gst_comm_p),
            "ad_spend":           _round2(ad_p),
            "penalty":            _round2(pen_p),
            "discount":           _round2(disc_p),
            "kept":               _round2(kept_p),
            "eff_pct":            eff_pct_p,
            "paisa":              paisa_p,    # integer — "27 paisa per rupee"
        }

    result["platform_earnings"] = platform_earnings

    # ── H-O4: True Order Margin (per platform) ────────────────────────────────
    food_cost_online = float(frames.purchases["total_cost"].fillna(0).sum()) if not frames.purchases.empty else 0.0
    gross_all_online = gross_total
    by_platform: dict[str, dict] = {}

    for platform in ["swiggy", "zomato"]:
        if df.empty:
            continue
        pf = df[df["source_type"] == platform]
        if pf.empty:
            continue
        order_count = pf["order_id"].nunique() if "order_id" in pf.columns else len(pf)
        if order_count == 0:
            continue

        gross_p     = float(pf["gross_amount"].fillna(0).sum())
        avg_gross   = _safe_div(gross_p, order_count)
        avg_comm    = -_safe_div(float(pf["commission"].fillna(0).sum()), order_count)
        avg_gst_c   = -_safe_div(float(pf["gst_on_commission"].fillna(0).sum()) or _gst_on_commission(-avg_comm * order_count), order_count)
        avg_ad      = -_safe_div(float(pf["ad_spend"].fillna(0).sum()), order_count)
        avg_pkg     = -_packaging_cost(avg_gross, config)
        # Proportional food cost allocation
        food_share  = _safe_div(gross_p, gross_all_online) if gross_all_online > 0 else 0
        avg_food    = -_safe_div(food_cost_online * food_share, order_count)
        avg_pocket  = avg_gross + avg_comm + avg_gst_c + avg_ad + avg_pkg + avg_food

        by_platform[platform] = {
            "avg_gross":          _round2(avg_gross),
            "avg_commission":     _round2(avg_comm),
            "avg_gst_on_comm":    _round2(avg_gst_c),
            "avg_ad_spend":       _round2(avg_ad),
            "avg_packaging":      _round2(avg_pkg),
            "avg_food_cost":      _round2(avg_food),
            "avg_pocket":         _round2(avg_pocket),
            "order_count":        order_count,
            "pkg_configured":     config.pkg_configured,
        }

    result["true_order_margin"] = {"by_platform": by_platform}

    # ── H-O5: Penalties — 3-State Classification ─────────────────────────────
    from app.models.records import classify_penalty

    recoverable_orders  = []
    non_recoverable_amt = 0.0
    non_recoverable_cnt = 0
    review_required_amt = 0.0
    review_required_cnt = 0

    if not df.empty:
        penalty_df = df[df["penalty"].fillna(0) > 0].copy()
        for _, row in penalty_df.iterrows():
            state = classify_penalty(
                str(row.get("source_type", "")),
                str(row.get("reason_code", "")) if pd.notna(row.get("reason_code")) else None,
            )
            pen_amt = float(row.get("penalty", 0) or 0)
            if state == "recoverable":
                recoverable_orders.append({
                    "id":       str(row.get("order_id", "")),
                    "date":     pd.to_datetime(row["date"]).date().isoformat() if pd.notna(row.get("date")) else "",
                    "platform": str(row.get("source_type", "")),
                    "amount":   _round2(pen_amt),
                    "reason":   str(row.get("reason_code", "")),
                    "evidence": f"Delivery time penalty — reason: {row.get('reason_code', 'unknown')}",
                })
            elif state == "non_recoverable":
                non_recoverable_amt += pen_amt
                non_recoverable_cnt += 1
            else:
                review_required_amt += pen_amt
                review_required_cnt += 1

    result["penalties"] = {
        "recoverable": {
            "amount": _round2(sum(o["amount"] for o in recoverable_orders)),
            "count":  len(recoverable_orders),
            "orders": recoverable_orders[:50],  # cap at 50 for payload size
        },
        "non_recoverable": {
            "amount": _round2(non_recoverable_amt),
            "count":  non_recoverable_cnt,
        },
        "review_required": {
            "amount": _round2(review_required_amt),
            "count":  review_required_cnt,
        },
    }

    # ── H-O6: Ad Spend Efficiency ─────────────────────────────────────────────
    blended_pocket = 0.0
    total_orders   = 0
    for p_data in by_platform.values():
        blended_pocket += p_data["avg_pocket"] * p_data["order_count"]
        total_orders   += p_data["order_count"]
    avg_pocket_blended = _safe_div(blended_pocket, total_orders)

    result["ad_spend_efficiency"] = {
        "total_ad_spend":  _round2(ad_spend_total),
        "gross_per_100":   _round2(_safe_div(gross_total, ad_spend_total) * 100) if ad_spend_total > 0 else None,
        "profit_per_100":  _round2(_safe_div(avg_pocket_blended * total_orders, ad_spend_total) * 100) if ad_spend_total > 0 else None,
    }

    # ── H-O7: Item Channel Margin ─────────────────────────────────────────────
    item_margins = []
    if _has_items(frames) and not df.empty and "item_name" in df.columns:
        item_costs = dict(zip(frames.items["item_name"], frames.items["standard_cost"]))
        top_items = (
            df.groupby("item_name")["order_id"].count()
            .sort_values(ascending=False)
            .head(10)
            .index.tolist()
        )
        dinein_df = frames.sales[frames.sales["channel"] == "dine_in"] if not frames.sales.empty else pd.DataFrame()

        for item in top_items:
            std_cost = item_costs.get(item)
            if std_cost is None:
                continue

            # Dine-in margin
            dinein_row = dinein_df[dinein_df["item_name"] == item] if not dinein_df.empty else pd.DataFrame()
            dinein_price = float(dinein_row["unit_price"].mean()) if not dinein_row.empty else None
            dinein_margin = _round2(_safe_div(dinein_price - std_cost, dinein_price) * 100) if dinein_price else None

            # Per-platform margins
            per_plat = {}
            for plat in ["swiggy", "zomato"]:
                plat_row = df[(df["source_type"] == plat) & (df["item_name"] == item)]
                if plat_row.empty:
                    continue
                plat_price = float(plat_row["unit_price"].mean())
                plat_comm  = _safe_div(float(platform_earnings.get(plat, {}).get("commission", 0)),
                                        float(platform_earnings.get(plat, {}).get("gross", 1)))
                net_price  = plat_price * (1 - plat_comm) - _packaging_cost(plat_price, config)
                plat_margin = _round2(_safe_div(net_price - std_cost, plat_price) * 100) if plat_price > 0 else None
                per_plat[plat] = plat_margin

            # Action tag logic
            worst_plat_margin = min((v for v in per_plat.values() if v is not None), default=None)
            best_dinein = dinein_margin or 0
            action_tag = "OK"
            if worst_plat_margin is not None:
                if worst_plat_margin < 0:
                    action_tag = "Consider Removing"
                elif (best_dinein - worst_plat_margin) > 25:
                    action_tag = "Price Up"

            item_margins.append({
                "item":                 item,
                "dine_in_margin_pct":   dinein_margin,
                "swiggy_margin_pct":    per_plat.get("swiggy"),
                "zomato_margin_pct":    per_plat.get("zomato"),
                "action_tag":           action_tag,
            })

    result["item_channel_margin"] = item_margins
    result["packaging_cost_config"] = {
        "tier1_below_150": config.pkg_tier1,
        "tier2_150_to_400": config.pkg_tier2,
        "tier3_above_400":  config.pkg_tier3,
        "is_configured":    config.pkg_configured,
    }

    return result


# ── LAYER 1 + 2 (SHARED — hybrid only) ────────────────────────────────────────

def compute_shared_block(
    dinein_result: dict,
    online_result: dict,
    frames: MetricFrames,
    config: OutletConfig,
) -> dict:
    """
    Computes Layer 1 (whole business) and Layer 2 (channel comparison).
    Always visible in hybrid dashboard regardless of active tab.
    """
    payout_bridge  = online_result.get("payout_bridge", {})
    gross_online   = payout_bridge.get("gross_revenue", 0) or 0
    kept_online    = payout_bridge.get("actual_payout",  0) or 0

    gross_dinein   = float(frames.sales[
        frames.sales["channel"].isin(["dine_in","takeaway"]) &
        ~frames.sales["is_deduplicated"].fillna(False)
    ]["gross_amount"].fillna(0).sum()) if not frames.sales.empty else 0.0
    kept_dinein    = gross_dinein   # no platform deductions for dine-in

    total_earnings = kept_dinein + kept_online
    gross_total    = gross_dinein + gross_online

    # Staff cost
    staff_cost_total = dinein_result.get("staff_cost_total", 0) or 0
    staff_cost_pct   = _round2(_safe_div(staff_cost_total, total_earnings) * 100) if total_earnings > 0 else None

    # Prime cost (whole business)
    prime_breakdown = dinein_result.get("prime_cost_breakdown", {})
    prime_cost_pct  = dinein_result.get("prime_cost_pct")

    # Kitchen conflict days
    kitchen_conflict_days = _compute_kitchen_conflict_days(frames)

    # ── Layer 2: "For every ₹100 earned" channel comparison ──────────────────
    food_cost_total   = prime_breakdown.get("food_cost", 0) or 0
    platform_cut      = gross_online - kept_online
    pkg_total_online  = _estimate_packaging_total(frames, config)

    # Proportional food cost allocation
    di_food_share = _safe_div(gross_dinein, gross_total)
    on_food_share = _safe_div(gross_online, gross_total)

    di_staff_share = _safe_div(gross_dinein, gross_total)
    on_staff_share = _safe_div(gross_online, gross_total)

    def _per_100(val: float, base: float) -> int:
        return round(_safe_div(val, base) * 100) if base > 0 else 0

    channel_comparison = {
        "dine_in": {
            "gross":           _round2(gross_dinein),
            "kept":            _round2(kept_dinein),
            "per_100_food":    _per_100(food_cost_total * di_food_share,  gross_dinein),
            "per_100_staff":   _per_100(staff_cost_total * di_staff_share, gross_dinein),
            "per_100_kept":    _per_100(kept_dinein, gross_dinein),
        },
        "online": {
            "gross":              _round2(gross_online),
            "kept":               _round2(kept_online),
            "per_100_platform":   _per_100(platform_cut,                   gross_online),
            "per_100_food":       _per_100(food_cost_total * on_food_share, gross_online),
            "per_100_packaging":  _per_100(pkg_total_online,               gross_online),
            "per_100_staff":      _per_100(staff_cost_total * on_staff_share, gross_online),
            "per_100_kept":       _per_100(kept_online,                    gross_online),
        },
    }

    return {
        "total_earnings":       _round2(total_earnings),
        "total_earnings_prev":  None,   # populated by period comparison
        "staff_cost_total":     _round2(staff_cost_total),
        "staff_cost_pct":       staff_cost_pct,
        "prime_cost_pct":       prime_cost_pct,
        "kitchen_conflict_days": kitchen_conflict_days,
        "channel_comparison":   channel_comparison,
    }


def _compute_kitchen_conflict_days(frames: MetricFrames) -> int:
    """
    Kitchen conflict = day where BOTH dine-in and online are simultaneously
    above their respective hourly averages by > 20%.
    Requires time-of-day granularity in records.
    """
    if frames.sales.empty or "date" not in frames.sales.columns:
        return 0
    if frames.sales["date"].dt.hour.nunique() <= 1:
        return 0   # no time-of-day data

    df = frames.sales[~frames.sales["is_deduplicated"].fillna(False)].copy()
    df["hour"]    = df["date"].dt.hour
    df["day"]     = df["date"].dt.date
    df["is_dinein"] = df["channel"].isin(["dine_in", "takeaway"])

    dinein_hourly = df[df["is_dinein"]].groupby(["day","hour"])["net_payout"].sum()
    online_hourly = df[~df["is_dinein"]].groupby(["day","hour"])["order_id"].count()

    if dinein_hourly.empty or online_hourly.empty:
        return 0

    di_avg = dinein_hourly.mean()
    on_avg = online_hourly.mean()
    if di_avg == 0 or on_avg == 0:
        return 0

    conflict_days = set()
    for (day, hour), di_val in dinein_hourly.items():
        on_val = online_hourly.get((day, hour), 0)
        if di_val > di_avg * 1.2 and on_val > on_avg * 1.2:
            conflict_days.add(day)

    return len(conflict_days)


def _estimate_packaging_total(frames: MetricFrames, config: OutletConfig) -> float:
    """Estimate total packaging cost using 3-tier model."""
    if frames.sales.empty:
        return 0.0
    online_df = frames.sales[frames.sales["channel"].isin(["swiggy","zomato"])].copy()
    if online_df.empty:
        return 0.0
    total_pkg = online_df["gross_amount"].fillna(0).apply(
        lambda v: _packaging_cost(v, config)
    ).sum()
    return float(total_pkg)


# ── CA EXPORT DATA ────────────────────────────────────────────────────────────

def compute_ca_export_block(frames: MetricFrames, config: OutletConfig) -> dict:
    """
    Builds the data for the CA Export (GST Reconciliation Report).
    Scope: structured data only — NOT a GST filing.
    """
    if frames.sales.empty:
        return {}

    # Data completeness
    completeness = {
        "swiggy":   not frames.sales[frames.sales["source_type"] == "swiggy"].empty,
        "zomato":   not frames.sales[frames.sales["source_type"] == "zomato"].empty,
        "petpooja": not frames.sales[frames.sales["source_type"] == "petpooja"].empty,
        "tally":    not frames.purchases.empty,
        "payroll":  not frames.labor.empty,
    }

    # Section 1: Revenue (GSTR-1 input)
    gross_total   = float(frames.sales["gross_amount"].fillna(0).sum())
    gst_rate      = config.gst_rate_pct / 100
    taxable_value = _round2(gross_total / (1 + gst_rate))
    gst_amount    = _round2(gross_total - taxable_value)

    # Section 2: Commission (GSTR-3B reverse charge)
    commission_total = float(frames.sales["commission"].fillna(0).sum())
    gst_on_comm      = _round2(_gst_on_commission(commission_total))
    by_platform_comm = {}
    for plat in ["swiggy","zomato"]:
        pf = frames.sales[frames.sales["source_type"] == plat]
        if pf.empty: continue
        c = float(pf["commission"].fillna(0).sum())
        by_platform_comm[plat] = {
            "commission":         _round2(c),
            "gst_on_commission":  _round2(_gst_on_commission(c)),
        }

    # Section 3: Packaging ITC
    pkg_total      = _estimate_packaging_total(frames, config)
    potential_itc  = _round2(pkg_total * 0.18)

    # Section 4: Reconciliation gap
    petpooja_total = float(frames.sales[
        frames.sales["source_type"] == "petpooja"
    ]["gross_amount"].fillna(0).sum())
    online_df = frames.sales[frames.sales["channel"].isin(["swiggy","zomato"])]
    settled_total = float(online_df[online_df["settled"].fillna(False)]["net_payout"].fillna(0).sum())
    gap = _round2(petpooja_total - settled_total) if petpooja_total > 0 else 0.0

    return {
        "completeness":                      completeness,
        "gst_on_sales": {
            "taxable_value": taxable_value,
            "gst_rate_pct":  config.gst_rate_pct,
            "gst_amount":    gst_amount,
        },
        "gst_on_commission_reverse_charge": {
            "total_commission": _round2(commission_total),
            "gst_pct":          18,
            "liability":        gst_on_comm,
            "by_platform":      by_platform_comm,
        },
        "itc_on_packaging": {
            "packaging_cost":  _round2(pkg_total),
            "potential_itc":   potential_itc,
            "verified":        False,
            "note":            "Verify with vendor GST registration before claiming.",
        },
        "reconciliation_gap": {
            "petpooja_total": _round2(petpooja_total),
            "settled_total":  _round2(settled_total),
            "gap":            gap,
        },
    }


# ── SUFFICIENCY MAP ────────────────────────────────────────────────────────────

def build_sufficiency_map(
    frames: MetricFrames,
    config: OutletConfig,
    outlet_type: str,
) -> dict[str, str]:
    """
    Returns {metric_key: 'complete'|'estimated'|'locked'|'partial'} for all metrics.
    Used for dashboard badges and CA Export completeness header.
    """
    has_sales    = _has_sales(frames)
    has_purch    = _has_purchases(frames)
    has_labor    = _has_labor(frames)
    has_items    = _has_items(frames)
    has_cash     = _has_manual_cash(frames)
    has_di_sales = _has_sales(frames, ["dine_in","takeaway"])
    has_on_sales = _has_sales(frames, ["swiggy","zomato"])

    s: dict[str, str] = {}

    # Layer 1 shared
    s["total_earnings"]       = "complete" if has_sales else "locked"
    s["staff_cost_pct"]       = "complete" if has_labor else "locked"
    s["prime_cost_pct"]       = ("complete" if (has_purch and has_labor)
                                 else "estimated" if (not has_purch and has_labor)
                                 else "locked")
    s["kitchen_conflict_days"] = "complete" if has_sales else "locked"

    # Dine-in tab
    s["today_earnings"]       = "complete" if has_di_sales else "locked"
    s["cash_reconciliation"]  = "complete" if has_cash else "locked"
    s["avg_bill_per_table"]   = "complete" if has_di_sales else "locked"
    s["table_turns"]          = "complete" if has_di_sales else "locked"
    s["best_service"]         = "complete" if has_di_sales else "locked"
    s["revpash"]              = "complete" if (has_di_sales and config.seat_count > 0) else "locked"
    s["staff_role_breakdown"] = "complete" if has_labor else "locked"

    # Online tab
    s["pending_settlements"]  = "complete" if has_on_sales else "locked"
    s["payout_bridge"]        = "complete" if has_on_sales else "locked"
    s["platform_earnings"]    = "complete" if has_on_sales else "locked"
    s["true_order_margin"]    = ("complete" if (has_on_sales and has_purch)
                                 else "estimated" if has_on_sales
                                 else "locked")
    s["penalties"]            = "complete" if has_on_sales else "locked"
    s["ad_spend_efficiency"]  = "complete" if has_on_sales else "locked"
    s["item_channel_margin"]  = "complete" if (has_on_sales and has_items) else "locked"
    s["packaging_cost_config"] = "complete" if config.pkg_configured else "estimated"

    # CA Export
    completeness_count = sum([has_on_sales, has_di_sales, has_purch, has_labor])
    s["ca_export"] = "complete" if completeness_count >= 4 else "partial" if completeness_count >= 2 else "locked"

    return s


# ── ALERT GENERATION ──────────────────────────────────────────────────────────

def generate_alerts(result: dict, sufficiency: dict) -> list[dict]:
    """
    Evaluates alert rules against computed metrics.
    Returns list sorted by priority (P1 = most critical).
    Maximum ONE alert is surfaced as push notification per day.
    """
    alerts = []

    def _add(priority: int, metric: str, condition: str, message: str, color: str = "amber"):
        alerts.append({
            "priority":  priority,
            "metric":    metric,
            "condition": condition,
            "message":   message,
            "color":     color,
            "fired_today": False,
        })

    prime = result.get("prime_cost_pct") or result.get("dine_in", {}).get("prime_cost_pct")
    if prime is not None:
        if prime > 65:
            _add(1, "prime_cost_pct", "> 65",
                 f"CRITICAL: Kitchen + staff cost has crossed 65% ({prime:.1f}%). Immediate review needed.",
                 "red")
        elif prime > 60:
            _add(4, "prime_cost_pct", "60–65",
                 f"Kitchen + staff cost at {prime:.1f}%. You are {65 - prime:.1f}pp from the danger zone.",
                 "amber")

    # Pending settlement overdue
    for ps in (result.get("online", {}) or {}).get("pending_settlements", []):
        if ps.get("overdue"):
            _add(3, "pending_settlement", "overdue",
                 f"{ps['platform'].title()} settlement of {_format_inr(ps['amount'])} is overdue. Contact partner support.",
                 "red")

    # Payout bridge > 35% deduction
    bridge = (result.get("online", {}) or {}).get("payout_bridge", {})
    gross_b = bridge.get("gross_revenue", 0) or 0
    payout_b = bridge.get("actual_payout", 0) or 0
    if gross_b > 0:
        deduction_pct = (gross_b - payout_b) / gross_b * 100
        if deduction_pct > 35:
            _add(5, "payout_bridge", "> 35% deduction",
                 f"Platform costs are consuming {deduction_pct:.0f}% of your gross revenue this month.",
                 "amber")

    # Staff cost %
    staff_pct = result.get("staff_cost_pct") or (result.get("dine_in", {}) or {}).get("staff_cost_pct")
    if staff_pct and staff_pct > 35:
        _add(6, "staff_cost_pct", "> 35",
             f"Staff costing ₹{staff_pct:.0f} per ₹100 earned. Review staffing levels.",
             "amber")

    # True order margin low (per platform)
    for plat, pd_data in (result.get("online", {}) or {}).get("true_order_margin", {}).get("by_platform", {}).items():
        pocket = pd_data.get("avg_pocket", 0) or 0
        if 0 < pocket < 80:
            _add(7, "true_order_margin", f"< 80 on {plat}",
                 f"You are keeping less than ₹80 per {plat.title()} order after all costs (₹{pocket:.0f}).",
                 "amber")

    # Recoverable penalties
    rec = (result.get("online", {}) or {}).get("penalties", {}).get("recoverable", {})
    rec_amt = rec.get("amount", 0) or 0
    rec_cnt = rec.get("count", 0) or 0
    if rec_amt > 0:
        _add(8, "penalties.recoverable", "> 0",
             f"₹{rec_amt:,.0f} in recoverable penalties ({rec_cnt} orders). Dispute list ready.",
             "green")

    # Review required penalties
    rev_cnt = (result.get("online", {}) or {}).get("penalties", {}).get("review_required", {}).get("count", 0) or 0
    if rev_cnt > 5:
        _add(9, "penalties.review_required", "> 5",
             f"{rev_cnt} penalties need manual review — reason code unclear.",
             "amber")

    # Cash reconciliation gap
    gaps = (result.get("dine_in", {}) or {}).get("cash_reconciliation", {}).get("daily_gaps", [])
    for g in gaps:
        if abs(g.get("gap", 0)) > 500:
            _add(12, "cash_reconciliation", "> ₹500 gap",
                 f"₹{abs(g['gap']):,.0f} cash gap on {g['date']}. Check with manager.",
                 "amber")
            break   # only one cash alert per day

    return sorted(alerts, key=lambda x: x["priority"])


# ── MAIN ENTRY POINT ──────────────────────────────────────────────────────────

def compute_metrics(frames: MetricFrames, config: OutletConfig) -> dict:
    """
    Main entry point called by run_compute_job.
    Returns the full result dict stored in metric_snapshots.result.
    """
    outlet_type = config.outlet_type
    result: dict[str, Any] = {
        "outlet_type":  outlet_type,
        "period_start": frames.date_from.isoformat() if frames.date_from else None,
        "period_end":   frames.date_to.isoformat()   if frames.date_to   else None,
    }

    if outlet_type == "dine_in":
        dinein = compute_dine_in_block(frames, config)
        result.update(dinein)

    elif outlet_type == "hybrid":
        dinein = compute_dine_in_block(frames, config)
        online = compute_online_block(frames, config)
        shared = compute_shared_block(dinein, online, frames, config)
        result.update(shared)
        result["dine_in"] = dinein
        result["online"]  = online

    elif outlet_type == "cloud_kitchen":
        online = compute_online_block(frames, config)
        result.update(online)
        # Cloud kitchen People metrics
        staff_cost_total = float(frames.labor["labor_cost"].fillna(0).sum()) if not frames.labor.empty else 0.0
        order_count      = frames.sales["order_id"].nunique() if not frames.sales.empty else 0
        avg_pocket_all   = 0.0
        for pd_data in online.get("true_order_margin", {}).get("by_platform", {}).values():
            avg_pocket_all += pd_data.get("avg_pocket", 0) * pd_data.get("order_count", 0)
        avg_pocket_all = _safe_div(avg_pocket_all, order_count) if order_count else 0

        monthly_fixed   = staff_cost_total + config.monthly_rent + config.monthly_utilities
        period_days     = (frames.date_to - frames.date_from).days + 1 if frames.date_from and frames.date_to else 30
        ck_daily_orders = _safe_div(order_count, period_days)
        breakeven       = _round2(_safe_div(monthly_fixed, avg_pocket_all * 30)) if avg_pocket_all > 0 else None

        result["staff_cost_total"]      = _round2(staff_cost_total)
        result["staff_cost_per_100_orders"] = _round2(_safe_div(staff_cost_total, order_count) * 100) if order_count else None
        result["break_even_orders_per_day"] = breakeven
        result["actual_avg_orders_per_day"] = _round2(ck_daily_orders)

    # CA Export — available for all outlet types
    result["ca_export"] = compute_ca_export_block(frames, config)

    # Sufficiency map
    sufficiency = build_sufficiency_map(frames, config, outlet_type)
    result["sufficiency"] = sufficiency

    # Alerts
    result["alerts"] = generate_alerts(result, sufficiency)

    return result
