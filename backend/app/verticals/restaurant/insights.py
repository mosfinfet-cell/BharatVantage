"""
restaurant/insights.py — Smart insight generation from computed metrics.
restaurant/actions.py  — Executable actions from metric state.
"""
from __future__ import annotations
from typing import List
from app.verticals.base import Insight, Action, MetricSufficiency


def generate_insights(result) -> List[Insight]:
    insights = []
    ny = result.net_yield
    pc = result.prime_cost
    pl = result.penalty_leakage
    dep= result.channel_dependency

    # Net Yield
    if ny and ny.net_margin_pct is not None:
        m = ny.net_margin_pct
        if m < 40:
            insights.append(Insight("warn", "💸", 1,
                f"Net margin critically low at {m:.1f}%",
                "After all platform deductions, you are keeping less than ₹40 per ₹100 earned. "
                "Review commission rates and ad spend urgently.", "raise_dispute"))
        elif m < 55:
            insights.append(Insight("warn", "⚠️", 2,
                f"Net margin below target at {m:.1f}%",
                f"Target is 55%+. Commission and ad spend are compressing your margins.", None))
        else:
            insights.append(Insight("good", "✅", 4,
                f"Healthy net margin at {m:.1f}%",
                "Platform deductions are within a sustainable range.", None))

        if not ny.used_actual_payout:
            insights.append(Insight("info", "📋", 3,
                "Commission estimated from default rates",
                "Upload your Swiggy and Zomato payout reports for exact commission figures.", None))

    # Prime Cost
    if pc and pc.prime_cost_pct is not None:
        pct = pc.prime_cost_pct
        if pc.status == "red":
            insights.append(Insight("warn", "🔴", 1,
                f"Prime Cost CRITICAL at {pct:.1f}%",
                "Food + labor costs exceed 65% of revenue. Audit portion sizes and shift scheduling immediately.",
                "flag_shift"))
        elif pc.status == "amber":
            insights.append(Insight("warn", "🟡", 2,
                f"Prime Cost elevated at {pct:.1f}%",
                "Approaching the danger zone. Reduce food waste or rationalise staff shifts to bring below 60%.", None))

    # Penalty Leakage
    if pl and pl.total_leakage and pl.total_leakage > 500:
        insights.append(Insight("warn", "🚨", 1,
            f"₹{pl.total_leakage:,.0f} lost to platform penalties",
            f"{pl.order_count} orders penalised. Dispute tickets can recover this cash.", "raise_dispute"))

    # Revenue Dependency
    for ch, pct in dep.items():
        if pct > 70:
            insights.append(Insight("warn", "⚠️", 2,
                f"{pct:.0f}% of revenue from {ch}",
                f"High dependency on {ch}. A commission hike or platform outage would severely impact your business.", None))

    # CAC comparison
    cac_s = result.cac_swiggy
    cac_z = result.cac_zomato
    if cac_s and cac_z and cac_s.cac and cac_z.cac:
        if cac_s.cac < cac_z.cac:
            diff = cac_z.cac - cac_s.cac
            insights.append(Insight("info", "📊", 3,
                "Swiggy has lower acquisition cost",
                f"CAC gap: ₹{diff:.0f}/customer. Shift ad spend towards Swiggy for better returns.", None))
        else:
            diff = cac_s.cac - cac_z.cac
            insights.append(Insight("info", "📊", 3,
                "Zomato has lower acquisition cost",
                f"CAC gap: ₹{diff:.0f}/customer. Shift ad spend towards Zomato for better returns.", None))

    insights.sort(key=lambda x: x.priority)
    return insights[:6]


def get_available_actions(result) -> List[Action]:
    actions = []

    # Dispute action — if penalty leakage above threshold
    pl = result.penalty_leakage
    if pl and pl.total_leakage and pl.total_leakage > 500:
        actions.append(Action(
            action_type = "raise_dispute",
            label       = f"Raise dispute for ₹{pl.total_leakage:,.0f} in penalties",
            payload     = {
                "total_amount": pl.total_leakage,
                "order_count":  pl.order_count,
                "top_orders":   pl.top_orders[:10],
                "by_channel":   pl.by_channel,
            },
            metric_ref  = "penalty_leakage",
        ))

    # Flag shift action — if prime cost is red
    pc = result.prime_cost
    if pc and pc.status == "red":
        actions.append(Action(
            action_type = "flag_shift",
            label       = "Flag high-cost shifts for review",
            payload     = {
                "prime_cost_pct": pc.prime_cost_pct,
                "total_labor":    pc.total_labor,
            },
            metric_ref  = "prime_cost",
        ))

    # Export report — always available
    actions.append(Action(
        action_type = "export_report",
        label       = "Export full analytics report",
        payload     = {},
        metric_ref  = "all",
    ))

    return actions
