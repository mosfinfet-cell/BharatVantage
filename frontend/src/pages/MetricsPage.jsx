/**
 * MetricsPage.jsx — BharatVantage v1.1 Dashboard
 *
 * Architecture:
 *   Layer 1: Whole business (total_earnings, staff_cost_pct, prime_cost_pct,
 *            kitchen_conflict_days) — ALWAYS visible
 *   Layer 2: Channel comparison ("every ₹100 earned") — ALWAYS visible (hybrid)
 *   Layer 3: Tab-based detail
 *            - Dine-in tab: cash reconciliation, table metrics, service analysis
 *            - Online tab: payout bridge, true margin, penalties, ad spend
 *            - People tab: staff cost, role breakdown, prime cost weekly
 *
 * Date range selector is GLOBAL — tab switching never resets the period.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft, RefreshCw, AlertTriangle, CheckCircle, Info,
  FileDown, MessageSquare, TrendingUp, TrendingDown,
  Clock, Users, ShoppingBag, Zap, ChevronRight,
} from "lucide-react";
import { compute as computeApi, actions as actionsApi, manualEntry } from "@/lib/api";
import { useAuth } from "@/store/AuthContext";
import Button from "@/components/ui/Button";

const POLL_MS = 3000;

// ── Sufficiency badge ──────────────────────────────────────────────────────
function SufficiencyBadge({ status }) {
  const cfg = {
    complete: { label: "Complete",              cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
    estimated:{ label: "Estimated",             cls: "bg-amber-500/10  text-amber-400  border-amber-500/20"  },
    locked:   { label: "Upload to unlock",      cls: "bg-zinc-700/30   text-zinc-400   border-zinc-600/30"   },
    partial:  { label: "Partial data",          cls: "bg-blue-500/10   text-blue-400   border-blue-500/20"   },
  }[status] || { label: status, cls: "bg-zinc-700/30 text-zinc-400" };
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

// ── Metric card ────────────────────────────────────────────────────────────
function MetricCard({ label, value, delta, deltaLabel, sufficiency, accent, children }) {
  return (
    <div className="card p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-[var(--text-secondary)] font-medium">{label}</span>
        {sufficiency && <SufficiencyBadge status={sufficiency} />}
      </div>
      {value !== undefined && value !== null ? (
        <div className={`text-2xl font-bold font-display ${accent || "text-[var(--text-primary)]"}`}>
          {value}
        </div>
      ) : (
        <div className="text-lg text-[var(--text-muted)] italic">—</div>
      )}
      {delta !== undefined && delta !== null && (
        <div className={`text-xs flex items-center gap-1 ${delta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
          {delta >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {deltaLabel || (delta >= 0 ? `+${fmt(delta)} vs last period` : `${fmt(delta)} vs last period`)}
        </div>
      )}
      {children}
    </div>
  );
}

// ── Alert banner ───────────────────────────────────────────────────────────
function AlertBanner({ alert }) {
  const cfg = {
    red:    { bg: "bg-red-500/10    border-red-500/30",    icon: "text-red-400",     ic: AlertTriangle },
    amber:  { bg: "bg-amber-500/10  border-amber-500/30",  icon: "text-amber-400",   ic: AlertTriangle },
    green:  { bg: "bg-emerald-500/10 border-emerald-500/30", icon: "text-emerald-400", ic: CheckCircle  },
    blue:   { bg: "bg-blue-500/10   border-blue-500/30",   icon: "text-blue-400",    ic: Info          },
  }[alert.color] || { bg: "bg-zinc-800 border-zinc-700", icon: "text-zinc-400", ic: Info };
  const Icon = cfg.ic;
  return (
    <div className={`flex items-start gap-3 px-4 py-3 rounded-xl border text-sm ${cfg.bg}`}>
      <Icon size={15} className={`mt-0.5 flex-shrink-0 ${cfg.icon}`} />
      <span className="text-[var(--text-primary)]">{alert.message}</span>
    </div>
  );
}

// ── Number formatters ──────────────────────────────────────────────────────
function fmt(val, type = "inr") {
  if (val === null || val === undefined) return "—";
  const n = Number(val);
  if (isNaN(n)) return "—";
  if (type === "inr") {
    if (Math.abs(n) >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
    if (Math.abs(n) >= 1000)   return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
    return `₹${n.toFixed(0)}`;
  }
  if (type === "pct") return `${n.toFixed(1)}%`;
  if (type === "num") return n.toLocaleString("en-IN");
  return String(n);
}

// ══════════════════════════════════════════════════════════════════════════
// LAYER 1: Whole Business
// ══════════════════════════════════════════════════════════════════════════
function Layer1({ metrics, sufficiency }) {
  const m = metrics || {};
  return (
    <div className="card p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="h-px flex-1 bg-[var(--border)]" />
        <span className="text-[10px] uppercase tracking-widest text-[var(--text-muted)] font-semibold px-2">
          Your whole business this month
        </span>
        <div className="h-px flex-1 bg-[var(--border)]" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Total Earnings"
          value={fmt(m.total_earnings)}
          delta={m.total_earnings && m.total_earnings_prev
            ? m.total_earnings - m.total_earnings_prev : undefined}
          deltaLabel={m.total_earnings_prev
            ? `${fmt(m.total_earnings - m.total_earnings_prev)} vs last month` : undefined}
          sufficiency={sufficiency?.total_earnings}
        />
        <MetricCard
          label="Staff Cost per ₹100 Earned"
          value={m.staff_cost_pct != null ? `₹${Math.round(m.staff_cost_pct)}` : null}
          sufficiency={sufficiency?.staff_cost_pct}
          accent={m.staff_cost_pct > 35 ? "text-amber-400" : "text-[var(--text-primary)]"}
        >
          {m.staff_cost_total != null && (
            <div className="text-xs text-[var(--text-muted)]">{fmt(m.staff_cost_total)} total</div>
          )}
        </MetricCard>
        <MetricCard
          label="Kitchen + Staff Cost %"
          value={m.prime_cost_pct != null ? fmt(m.prime_cost_pct, "pct") : null}
          sufficiency={sufficiency?.prime_cost_pct}
          accent={
            m.prime_cost_pct > 65 ? "text-red-400" :
            m.prime_cost_pct > 60 ? "text-amber-400" : "text-emerald-400"
          }
        >
          {m.prime_cost_pct > 65 && (
            <div className="text-xs text-red-400 font-semibold">⚠ Above danger zone</div>
          )}
          {m.prime_cost_pct > 60 && m.prime_cost_pct <= 65 && (
            <div className="text-xs text-amber-400">
              {(65 - m.prime_cost_pct).toFixed(1)}pp from limit
            </div>
          )}
        </MetricCard>
        <MetricCard
          label="Busy Overlap Days"
          value={m.kitchen_conflict_days ?? "—"}
          sufficiency={sufficiency?.kitchen_conflict_days}
        >
          <div className="text-xs text-[var(--text-muted)]">Dual-pressure evenings</div>
        </MetricCard>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// LAYER 2: Channel Comparison ("Every ₹100 Earned")
// ══════════════════════════════════════════════════════════════════════════
function Layer2({ channelComparison }) {
  if (!channelComparison) return null;
  const { dine_in: di, online: on } = channelComparison;

  const ChannelCol = ({ title, color, data, rows }) => (
    <div className="flex-1 p-4 rounded-xl bg-[var(--bg-subtle)]">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full" style={{ background: color }} />
        <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">
          {title}
        </span>
      </div>
      {rows.map(({ label, val, isKept }) => (
        <div key={label} className={`flex justify-between items-center py-1.5 border-b border-[var(--border)] text-sm
          ${isKept ? "font-bold border-0 mt-1" : ""}`}>
          <span className="text-[var(--text-secondary)]">{label}</span>
          <span className={`font-mono text-xs ${isKept ? "text-emerald-400 text-sm font-bold" :
            val < 0 ? "text-red-400" : "text-[var(--text-primary)]"}`}>
            {val < 0 ? `−₹${Math.abs(val)}` : `₹${val}`}
          </span>
        </div>
      ))}
    </div>
  );

  return (
    <div className="card p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="h-px flex-1 bg-[var(--border)]" />
        <span className="text-[10px] uppercase tracking-widest text-[var(--text-muted)] font-semibold px-2">
          For every ₹100 you earn — dine-in vs online
        </span>
        <div className="h-px flex-1 bg-[var(--border)]" />
      </div>
      <div className="flex gap-3">
        {di && (
          <ChannelCol title="Dine-in" color="#0D6B72" data={di} rows={[
            { label: "Gross earned",    val: 100 },
            { label: "Food cost",       val: -(di.per_100_food   || 0) },
            { label: "Staff share",     val: -(di.per_100_staff  || 0) },
            { label: "You keep",        val:   di.per_100_kept   || 0, isKept: true },
          ]} />
        )}
        {on && (
          <ChannelCol title="Online delivery" color="#5B21B6" data={on} rows={[
            { label: "Gross earned",    val: 100 },
            { label: "Platform fees",   val: -(on.per_100_platform   || 0) },
            { label: "Food cost",       val: -(on.per_100_food       || 0) },
            { label: "Packaging",       val: -(on.per_100_packaging  || 0) },
            { label: "Staff share",     val: -(on.per_100_staff      || 0) },
            { label: "You keep",        val:   on.per_100_kept       || 0, isKept: true },
          ]} />
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// DINE-IN TAB
// ══════════════════════════════════════════════════════════════════════════
function DineInTab({ data, sufficiency }) {
  const d = data || {};
  const cr = d.cash_reconciliation || {};

  return (
    <div className="flex flex-col gap-4">
      {/* Today's Earnings */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Dine-in Earnings Today"
          value={fmt(d.today_earnings)}
          delta={d.today_earnings && d.today_prev_same_weekday
            ? d.today_earnings - d.today_prev_same_weekday : undefined}
          deltaLabel={`vs last ${new Date(Date.now() - 7 * 86400000).toLocaleDateString("en-IN", { weekday: "long" })}`}
          sufficiency={sufficiency?.today_earnings}
        />
        <MetricCard
          label="Average Bill per Table"
          value={fmt(d.avg_bill_per_table)}
          sufficiency={sufficiency?.avg_bill_per_table}
        />
        <MetricCard
          label="RevPASH"
          value={d.revpash != null ? fmt(d.revpash) : null}
          sufficiency={sufficiency?.revpash}
        >
          <div className="text-xs text-[var(--text-muted)]">Per chair per hour</div>
        </MetricCard>
        <MetricCard
          label="Low-Footfall Days"
          value={d.floor_staff_low_days ?? "—"}
          sufficiency="complete"
        >
          <div className="text-xs text-[var(--text-muted)]">Floor staff underused</div>
        </MetricCard>
      </div>

      {/* Cash Reconciliation */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Cash vs UPI — Daily Check</h3>
          {cr.manual_entry_required && (
            <span className="text-xs text-amber-400 flex items-center gap-1">
              <AlertTriangle size={11} /> Enter today's cash to unlock gap
            </span>
          )}
        </div>
        <div className="flex gap-6 mb-4">
          <div>
            <div className="text-xl font-bold">{cr.cash_pct?.toFixed(0) ?? "—"}%</div>
            <div className="text-xs text-[var(--text-muted)]">Cash</div>
          </div>
          <div>
            <div className="text-xl font-bold">{cr.upi_pct?.toFixed(0) ?? "—"}%</div>
            <div className="text-xs text-[var(--text-muted)]">UPI / Card</div>
          </div>
        </div>
        {(cr.daily_gaps || []).length > 0 ? (
          <div className="space-y-1">
            {cr.daily_gaps.map((g) => (
              <div key={g.date} className="flex items-center justify-between text-xs px-3 py-2
                bg-red-500/10 border border-red-500/20 rounded-lg">
                <span className="text-[var(--text-secondary)]">{g.date}</span>
                <span className="text-red-400 font-mono font-semibold">
                  ₹{Math.abs(g.gap).toLocaleString("en-IN")} gap
                </span>
                <span className="text-[var(--text-muted)]">
                  Expected ₹{(g.expected || 0).toLocaleString("en-IN")} · Got ₹{(g.actual || 0).toLocaleString("en-IN")}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-emerald-400">✓ No cash gaps detected this month</div>
        )}
      </div>

      {/* Best / Worst Service */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {d.best_service && (
          <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/15">
            <div className="text-xs font-semibold text-emerald-400 mb-1">Best service this week</div>
            <div className="text-lg font-bold">{d.best_service.label}</div>
            <div className="text-sm text-emerald-400">{fmt(d.best_service.amount)}</div>
          </div>
        )}
        {d.worst_service && (
          <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/15">
            <div className="text-xs font-semibold text-red-400 mb-1">Worst service this week</div>
            <div className="text-lg font-bold">{d.worst_service.label}</div>
            <div className="text-sm text-red-400">{fmt(d.worst_service.amount)}</div>
          </div>
        )}
      </div>

      {/* Table turns */}
      {d.table_turns && Object.keys(d.table_turns).length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-3">Table Turns by Service</h3>
          <div className="space-y-1">
            {Object.entries(d.table_turns)
              .sort(([, a], [, b]) => b - a)
              .map(([label, turns]) => (
                <div key={label} className="flex items-center justify-between text-sm py-1.5
                  border-b border-[var(--border)] last:border-0">
                  <span className="text-[var(--text-secondary)]">{label}</span>
                  <span className="font-mono font-semibold">{turns}×</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// ONLINE TAB
// ══════════════════════════════════════════════════════════════════════════
function OnlineTab({ data, sufficiency, sessionId, token, outletId }) {
  const d = data || {};
  const [disputeLoading, setDisputeLoading] = useState(false);

  async function handleDispute() {
    const recoverableOrders = d.penalties?.recoverable?.orders || [];
    if (!recoverableOrders.length) return;
    setDisputeLoading(true);
    try {
      const result = await actionsApi.raiseDispute(token, outletId, {
        sessionId,
        orders: recoverableOrders,
      });
      alert(`Dispute raised. Template ID: ${result.dispute_id || "generated"}`);
    } catch (e) {
      alert("Failed to generate dispute: " + e.message);
    } finally {
      setDisputeLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Pending Settlements — FIRST CARD, always prominent */}
      {(d.pending_settlements || []).length > 0 && (
        <div className="card p-4 border-l-4 border-[var(--saffron)]">
          <h3 className="text-sm font-semibold mb-3">Money Owed to You</h3>
          <div className="grid grid-cols-2 gap-3">
            {d.pending_settlements.map((ps) => (
              <div key={ps.platform}
                className={`p-3 rounded-xl ${ps.overdue ? "bg-red-500/10 border border-red-500/20" : "bg-[var(--saffron-subtle)] border border-[var(--saffron-glow)]"}`}>
                <div className={`text-xs font-semibold mb-1 ${ps.overdue ? "text-red-400" : "text-[var(--saffron)]"}`}>
                  {ps.platform.charAt(0).toUpperCase() + ps.platform.slice(1)} owes you
                  {ps.overdue && " — OVERDUE"}
                </div>
                <div className="text-xl font-bold">{fmt(ps.amount)}</div>
                <div className="text-xs text-[var(--text-muted)] mt-1">
                  Expected {ps.expected_date}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Payout Bridge */}
      {d.payout_bridge && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">Where Your Online Money Goes</h3>
          <div className="space-y-0">
            {[
              { label: "Gross revenue",            key: "gross_revenue",          color: "bg-blue-500/30" },
              { label: "Platform commission",       key: "less_commission",         color: "bg-red-500/30"  },
              { label: "GST on commission (18%)",   key: "less_gst_on_commission", color: "bg-amber-500/30" },
              { label: "Ad spend",                  key: "less_ad_spend",          color: "bg-red-500/20"  },
              { label: "Discounts",                 key: "less_discounts",         color: "bg-red-500/15"  },
              { label: "Penalties",                 key: "less_penalties",         color: "bg-red-500/25"  },
              { label: "What actually reached you", key: "actual_payout",          color: "bg-emerald-500/30", bold: true },
            ].map(({ label, key, color, bold }) => {
              const val = d.payout_bridge[key];
              if (val === undefined || val === null) return null;
              const maxVal = Math.abs(d.payout_bridge.gross_revenue || 1);
              const barW = Math.min(100, Math.abs(val) / maxVal * 100);
              return (
                <div key={key} className={`flex items-center gap-3 py-2 border-b border-[var(--border)] last:border-0 ${bold ? "pt-3" : ""}`}>
                  <div className="w-36 text-xs text-[var(--text-secondary)] shrink-0">{label}</div>
                  <div className="flex-1 h-2 bg-[var(--bg-subtle)] rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${bold ? "bg-emerald-500" : color}`}
                      style={{ width: `${barW}%` }} />
                  </div>
                  <div className={`w-24 text-right font-mono text-xs font-semibold
                    ${bold ? "text-emerald-400 text-sm" : val < 0 ? "text-red-400" : "text-[var(--text-primary)]"}`}>
                    {val >= 0 ? fmt(val) : `−${fmt(Math.abs(val))}`}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* True Order Margin — per platform */}
      {d.true_order_margin?.by_platform && (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold">What You Pocket per Delivery Order</h3>
            <SufficiencyBadge status={sufficiency?.true_order_margin} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(d.true_order_margin.by_platform).map(([plat, pd]) => (
              <div key={plat} className="p-3 rounded-xl bg-[var(--bg-subtle)]">
                <div className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3">
                  {plat.charAt(0).toUpperCase() + plat.slice(1)}
                </div>
                {[
                  { label: "Gross order",         val: pd.avg_gross,       positive: true  },
                  { label: "Commission",           val: pd.avg_commission                   },
                  { label: "GST on commission",    val: pd.avg_gst_on_comm                  },
                  { label: "Ad spend",             val: pd.avg_ad_spend                     },
                  { label: "Packaging",            val: pd.avg_packaging                    },
                  { label: "Food cost",            val: pd.avg_food_cost                    },
                  { label: "Your pocket",          val: pd.avg_pocket,     isKept: true     },
                ].map(({ label, val, positive, isKept }) => (
                  <div key={label} className={`flex justify-between text-xs py-1 border-b border-[var(--border)] last:border-0
                    ${isKept ? "font-bold text-sm border-0 pt-2" : ""}`}>
                    <span className="text-[var(--text-secondary)]">{label}</span>
                    <span className={`font-mono ${isKept
                      ? (pd.avg_pocket >= 80 ? "text-emerald-400" : "text-amber-400")
                      : val < 0 ? "text-red-400" : "text-[var(--text-primary)]"}`}>
                      {val >= 0 ? `₹${Math.abs(val).toFixed(0)}` : `−₹${Math.abs(val).toFixed(0)}`}
                    </span>
                  </div>
                ))}
                {!pd.pkg_configured && (
                  <div className="text-[10px] text-amber-400 mt-2">
                    ⚠ Packaging estimated · configure in Settings
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Penalties — 3-state */}
      {d.penalties && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-3">Penalties — What You Can Get Back</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Recoverable */}
            <div className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
              <div className="text-xs font-semibold text-emerald-400 mb-1">You can get back</div>
              <div className="text-xl font-bold text-emerald-400">{fmt(d.penalties.recoverable?.amount)}</div>
              <div className="text-xs text-[var(--text-muted)] mb-3">
                {d.penalties.recoverable?.count || 0} orders · platform delays
              </div>
              {(d.penalties.recoverable?.count || 0) > 0 && (
                <Button
                  size="sm"
                  onClick={handleDispute}
                  disabled={disputeLoading}
                  className="w-full text-xs"
                >
                  {disputeLoading ? "Generating…" : "Generate dispute list →"}
                </Button>
              )}
            </div>

            {/* Non-recoverable */}
            <div className="p-3 rounded-xl bg-red-500/5 border border-red-500/20">
              <div className="text-xs font-semibold text-red-400 mb-1">Not recoverable</div>
              <div className="text-xl font-bold text-red-400">{fmt(d.penalties.non_recoverable?.amount)}</div>
              <div className="text-xs text-[var(--text-muted)]">
                {d.penalties.non_recoverable?.count || 0} orders · kitchen/prep issues
              </div>
            </div>

            {/* Review required */}
            {(d.penalties.review_required?.count || 0) > 0 && (
              <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
                <div className="text-xs font-semibold text-amber-400 mb-1">Check with platform</div>
                <div className="text-xl font-bold text-amber-400">{fmt(d.penalties.review_required?.amount)}</div>
                <div className="text-xs text-[var(--text-muted)]">
                  {d.penalties.review_required?.count} orders · reason unclear
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Platform earnings (paisa framing) */}
      {d.platform_earnings && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-3">Platform Earnings — Paisa per Rupee</h3>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(d.platform_earnings).map(([plat, pe]) => (
              <div key={plat} className="p-3 rounded-xl bg-[var(--bg-subtle)]">
                <div className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">
                  {plat.charAt(0).toUpperCase() + plat.slice(1)}
                </div>
                <div className="text-lg font-bold">{fmt(pe.gross)}</div>
                <div className="text-xs text-[var(--text-muted)] mb-2">gross</div>
                <div className="space-y-0.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Commission</span>
                    <span className="font-mono text-red-400">−{fmt(pe.commission)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">GST on comm.</span>
                    <span className="font-mono text-amber-400">−{fmt(pe.gst_on_commission)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Ads + penalties</span>
                    <span className="font-mono text-red-400">−{fmt((pe.ad_spend || 0) + (pe.penalty || 0))}</span>
                  </div>
                </div>
                <div className="mt-2 pt-2 border-t border-[var(--border)]">
                  <div className="text-sm font-bold text-emerald-400">{fmt(pe.kept)} kept</div>
                  <div className="text-xs text-blue-400 mt-0.5">{pe.paisa} paisa per rupee</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ad Spend Efficiency */}
      {d.ad_spend_efficiency?.total_ad_spend > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-2">Are Your Ads Making You Money?</h3>
          <div className="text-sm">
            You spent <span className="font-bold">{fmt(d.ad_spend_efficiency.total_ad_spend)}</span> on ads.{" "}
            Each ₹100 of ad spend brought{" "}
            <span className="font-bold">{fmt(d.ad_spend_efficiency.gross_per_100)}</span> in orders and{" "}
            <span className={`font-bold ${(d.ad_spend_efficiency.profit_per_100 || 0) >= 15 ? "text-emerald-400" : "text-amber-400"}`}>
              {fmt(d.ad_spend_efficiency.profit_per_100)}
            </span>{" "}in profit.
          </div>
        </div>
      )}

      {/* Item Channel Margin */}
      {(d.item_channel_margin || []).length > 0 && (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Which Items Make More Money Dine-in vs Online</h3>
            <span className="text-xs text-[var(--text-muted)]">Top {d.item_channel_margin.length} items</span>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[var(--text-muted)] border-b border-[var(--border)]">
                <th className="text-left py-2">Item</th>
                <th className="text-right py-2">Dine-in</th>
                <th className="text-right py-2">Swiggy</th>
                <th className="text-right py-2">Zomato</th>
                <th className="text-right py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {d.item_channel_margin.map((it) => (
                <tr key={it.item} className="border-b border-[var(--border)] last:border-0">
                  <td className="py-2 text-[var(--text-primary)]">{it.item}</td>
                  <td className="py-2 text-right font-mono text-emerald-400">
                    {it.dine_in_margin_pct != null ? `${it.dine_in_margin_pct}%` : "—"}
                  </td>
                  <td className="py-2 text-right font-mono text-[var(--text-secondary)]">
                    {it.swiggy_margin_pct != null ? `${it.swiggy_margin_pct}%` : "—"}
                  </td>
                  <td className="py-2 text-right font-mono text-[var(--text-secondary)]">
                    {it.zomato_margin_pct != null ? `${it.zomato_margin_pct}%` : "—"}
                  </td>
                  <td className="py-2 text-right">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      it.action_tag === "Price Up" ? "bg-amber-500/10 text-amber-400" :
                      it.action_tag === "Consider Removing" ? "bg-red-500/10 text-red-400" :
                      "bg-emerald-500/10 text-emerald-400"
                    }`}>
                      {it.action_tag}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// PEOPLE TAB
// ══════════════════════════════════════════════════════════════════════════
function PeopleTab({ dineInData, metrics, sufficiency }) {
  const d = dineInData || metrics || {};
  const roles = d.staff_role_breakdown || [];
  const primeBreakdown = d.prime_cost_breakdown || {};

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          label="Staff Cost This Month"
          value={fmt(d.staff_cost_total || metrics?.staff_cost_total)}
          sufficiency={sufficiency?.staff_cost_pct}
        >
          <div className="text-xs text-[var(--text-muted)] mt-1">Monthly salaries total</div>
        </MetricCard>
        <MetricCard
          label="Staff Cost per ₹100 Earned"
          value={d.staff_cost_pct != null
            ? `₹${Math.round(d.staff_cost_pct)}`
            : metrics?.staff_cost_pct != null
              ? `₹${Math.round(metrics.staff_cost_pct)}`
              : null}
          sufficiency={sufficiency?.staff_cost_pct}
          accent={(d.staff_cost_pct || metrics?.staff_cost_pct) > 35 ? "text-amber-400" : "text-emerald-400"}
        />
        <MetricCard
          label="Prime Cost %"
          value={fmt(d.prime_cost_pct || metrics?.prime_cost_pct, "pct")}
          sufficiency={sufficiency?.prime_cost_pct}
          accent={
            (d.prime_cost_pct || metrics?.prime_cost_pct) > 65 ? "text-red-400" :
            (d.prime_cost_pct || metrics?.prime_cost_pct) > 60 ? "text-amber-400" : "text-emerald-400"
          }
        />
      </div>

      {/* Role breakdown */}
      {roles.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-3">Where Your Staff Cost Goes</h3>
          <div className="space-y-2">
            {roles.map((r) => (
              <div key={r.role} className="flex items-center gap-3">
                <div className="w-32 text-xs text-[var(--text-secondary)] capitalize">{r.role}</div>
                <div className="flex-1 h-2 bg-[var(--bg-subtle)] rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-[var(--saffron)]"
                    style={{ width: `${r.pct}%` }} />
                </div>
                <div className="w-20 text-right font-mono text-xs">{fmt(r.amount)}</div>
                <div className="w-12 text-right text-xs text-[var(--text-muted)]">{r.pct?.toFixed(0)}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Prime cost breakdown */}
      {primeBreakdown.total > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-3">Prime Cost Breakdown</h3>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <div className="text-lg font-bold text-[var(--saffron)]">{fmt(primeBreakdown.food_cost)}</div>
              <div className="text-xs text-[var(--text-muted)]">Food cost</div>
            </div>
            <div>
              <div className="text-lg font-bold text-blue-400">{fmt(primeBreakdown.staff_cost)}</div>
              <div className="text-xs text-[var(--text-muted)]">Staff cost</div>
            </div>
            <div>
              <div className="text-lg font-bold">{fmt(primeBreakdown.total)}</div>
              <div className="text-xs text-[var(--text-muted)]">Combined</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CA EXPORT
// ══════════════════════════════════════════════════════════════════════════
function CAExportTab({ caData, sufficiency, sessionId, token, outletId }) {
  const d = caData || {};
  const [exportLoading, setExportLoading] = useState(false);

  async function handleExport() {
    setExportLoading(true);
    try {
      const result = await actionsApi.exportCA(token, outletId, {
        sessionId, format: "pdf",
      });
      if (result.download_url) {
        window.open(result.download_url, "_blank");
      } else {
        alert("Export queued. Check back in a moment.");
      }
    } catch (e) {
      alert("Export failed: " + e.message);
    } finally {
      setExportLoading(false);
    }
  }

  const completeness = d.completeness || {};
  const sources = [
    { key: "swiggy",   label: "Swiggy settlement" },
    { key: "zomato",   label: "Zomato settlement" },
    { key: "petpooja", label: "Petpooja POS" },
    { key: "tally",    label: "Tally purchase data" },
    { key: "payroll",  label: "Payroll data" },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* Completeness header */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Data Completeness</h3>
          <SufficiencyBadge status={sufficiency?.ca_export} />
        </div>
        <div className="space-y-1 mb-4">
          {sources.map((s) => (
            <div key={s.key} className="flex items-center gap-2 text-xs">
              <span className={completeness[s.key] ? "text-emerald-400" : "text-[var(--text-muted)]"}>
                {completeness[s.key] ? "✓" : "⚠"}
              </span>
              <span className={completeness[s.key] ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"}>
                {s.label}
              </span>
              {!completeness[s.key] && (
                <span className="text-amber-400 text-[10px]">(missing — values estimated)</span>
              )}
            </div>
          ))}
        </div>
        <div className="text-xs text-[var(--text-muted)] mb-4">
          Share with your CA noting any missing sources before filing GSTR-1 and GSTR-3B.
        </div>
        <Button onClick={handleExport} disabled={exportLoading} className="w-full">
          <FileDown size={14} />
          {exportLoading ? "Generating…" : "Download CA Report (PDF)"}
        </Button>
      </div>

      {/* GST on Sales */}
      {d.gst_on_sales && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-3">Revenue Summary (GSTR-1 Input)</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Total Gross Revenue</span><span className="font-mono font-bold">{fmt(d.gst_on_sales.taxable_value + d.gst_on_sales.gst_amount)}</span></div>
            <div className="flex justify-between"><span className="text-[var(--text-secondary)]">GST Rate</span><span className="font-mono">{d.gst_on_sales.gst_rate_pct}%</span></div>
            <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Taxable Value</span><span className="font-mono">{fmt(d.gst_on_sales.taxable_value)}</span></div>
            <div className="flex justify-between border-t border-[var(--border)] pt-2"><span className="text-[var(--text-secondary)]">Output GST (collected)</span><span className="font-mono font-bold text-[var(--saffron)]">{fmt(d.gst_on_sales.gst_amount)}</span></div>
          </div>
        </div>
      )}

      {/* GST on Commission (Reverse Charge) */}
      {d.gst_on_commission_reverse_charge && (
        <div className="card p-4 border border-amber-500/20">
          <h3 className="text-sm font-semibold mb-1">Platform Commission (GSTR-3B — Reverse Charge)</h3>
          <p className="text-xs text-amber-400 mb-3">
            You owe 18% GST on aggregator commissions under reverse charge.
            Your CA must include this in GSTR-3B Table 3.1(d).
          </p>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Total Commission Paid</span><span className="font-mono">{fmt(d.gst_on_commission_reverse_charge.total_commission)}</span></div>
            <div className="flex justify-between border-t border-[var(--border)] pt-2">
              <span className="text-[var(--text-secondary)]">GST Liability (18%)</span>
              <span className="font-mono font-bold text-amber-400">{fmt(d.gst_on_commission_reverse_charge.liability)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Reconciliation Gap */}
      {d.reconciliation_gap?.gap > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-3">Reconciliation Gap</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Petpooja Total</span><span className="font-mono">{fmt(d.reconciliation_gap.petpooja_total)}</span></div>
            <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Settled by Platforms</span><span className="font-mono">{fmt(d.reconciliation_gap.settled_total)}</span></div>
            <div className="flex justify-between border-t border-[var(--border)] pt-2">
              <span className="text-[var(--text-secondary)]">Missing Money</span>
              <span className="font-mono font-bold text-red-400">{fmt(d.reconciliation_gap.gap)}</span>
            </div>
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-2">
            Revenue recognised in books but not yet received. CA to treat as receivable.
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════════
export default function MetricsPage() {
  const { sessionId } = useParams();
  const { token, outletId } = useAuth();
  const [status, setStatus]     = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [activeTab, setActiveTab] = useState("dine_in");
  const pollRef = useRef(null);

  const stopPolling = () => { if (pollRef.current) clearInterval(pollRef.current); };

  const fetchMetrics = useCallback(async () => {
    try {
      const data = await computeApi.getMetrics(token, outletId, sessionId);
      if (data.__status !== 202) {
        setSnapshot(data);
        stopPolling();
        setLoading(false);
      }
    } catch (e) {
      console.error("metrics fetch error:", e);
    }
  }, [token, outletId, sessionId]);

  const pollStatus = useCallback(async () => {
    try {
      const s = await computeApi.getStatus(token, outletId, sessionId);
      setStatus(s);
      if (s.ready) {
        stopPolling();
        await fetchMetrics();
      }
    } catch (e) {
      console.error("status poll error:", e);
    }
  }, [token, outletId, sessionId, fetchMetrics]);

  useEffect(() => {
    pollStatus();
    pollRef.current = setInterval(pollStatus, POLL_MS);
    return stopPolling;
  }, [pollStatus]);

  const metrics = snapshot?.metrics || {};
  const suf     = snapshot?.sufficiency || {};
  const alerts  = snapshot?.alerts || [];
  const outletType = snapshot?.outlet_type || "hybrid";

  // Set default tab based on outlet type
  useEffect(() => {
    if (outletType === "cloud_kitchen") setActiveTab("online");
    else if (outletType === "dine_in")  setActiveTab("dine_in");
    else setActiveTab("dine_in");
  }, [outletType]);

  const tabs = [
    ...(outletType !== "cloud_kitchen" ? [{ id: "dine_in",  label: "Dine-in"   }] : []),
    ...(outletType !== "dine_in"       ? [{ id: "online",   label: "Online"    }] : []),
    { id: "people",  label: "People"    },
    { id: "ca",      label: "CA Export" },
  ];

  if (loading && !snapshot) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <RefreshCw className="animate-spin text-[var(--saffron)]" size={28} />
        <div className="text-sm text-[var(--text-secondary)]">
          {status?.compute_status === "queued"   && "Computing your metrics…"}
          {status?.compute_status === "running"  && "Almost ready…"}
          {!status?.compute_status               && "Loading…"}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link to="/dashboard" className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-1">
            <ArrowLeft size={12} /> Dashboard
          </Link>
          <h1 className="text-xl font-bold font-display">Analytics Report</h1>
          {snapshot && (
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              {snapshot.period_start} → {snapshot.period_end}
              {" · "}
              <span className="capitalize">{outletType.replace("_", "-")}</span>
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {snapshot?.is_stale && (
            <span className="text-xs text-amber-400 border border-amber-500/30 px-2 py-1 rounded-lg">
              Recalculate available
            </span>
          )}
        </div>
      </div>

      {/* Top alert */}
      {alerts.length > 0 && <AlertBanner alert={alerts[0]} />}

      {/* LAYER 1 — always visible */}
      {(outletType === "hybrid" || outletType === "dine_in") && (
        <Layer1 metrics={metrics} sufficiency={suf} />
      )}

      {/* LAYER 2 — channel comparison (hybrid only) */}
      {outletType === "hybrid" && metrics.channel_comparison && (
        <Layer2 channelComparison={metrics.channel_comparison} />
      )}

      {/* LAYER 3 — tab bar (globally synced date range) */}
      <div className="flex items-center justify-between">
        <div className="flex bg-[var(--bg-elevated)] rounded-xl p-1 gap-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all
                ${activeTab === t.id
                  ? "bg-[var(--bg-base)] text-[var(--text-primary)] shadow-sm"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <span className="text-[10px] text-[var(--text-muted)]">
          {snapshot?.period_start} – {snapshot?.period_end}
        </span>
      </div>

      {/* Tab content */}
      <div>
        {activeTab === "dine_in" && (
          <DineInTab
            data={metrics.dine_in || metrics}
            sufficiency={suf}
          />
        )}
        {activeTab === "online" && (
          <OnlineTab
            data={metrics.online || metrics}
            sufficiency={suf}
            sessionId={sessionId}
            token={token}
            outletId={outletId}
          />
        )}
        {activeTab === "people" && (
          <PeopleTab
            dineInData={metrics.dine_in}
            metrics={metrics}
            sufficiency={suf}
          />
        )}
        {activeTab === "ca" && (
          <CAExportTab
            caData={metrics.ca_export}
            sufficiency={suf}
            sessionId={sessionId}
            token={token}
            outletId={outletId}
          />
        )}
      </div>

      {/* Remaining alerts tray */}
      {alerts.length > 1 && (
        <div className="card p-4">
          <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">
            Other alerts
          </h3>
          <div className="flex flex-col gap-2">
            {alerts.slice(1).map((a, i) => <AlertBanner key={i} alert={a} />)}
          </div>
        </div>
      )}
    </div>
  );
}
