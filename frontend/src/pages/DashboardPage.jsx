// pages/DashboardPage.jsx
//
// Reasoning: Dashboard is the homepage post-login. It shows:
// 1. Summary stats across sessions
// 2. Most recent MetricSnapshot (calls GET /metrics/:sessionId)
// 3. Quick-access upload CTA if no sessions exist
// 4. Recent activity timeline
//
// For the first load, we poll GET /status/:sessionId if compute is running.

import React, { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Upload, RefreshCw, ArrowRight, TrendingUp, TrendingDown,
  AlertCircle, CheckCircle, Clock, Zap, FileText, ChevronRight
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts'
import { compute as computeApi } from '@/lib/api'
import { useAuth } from '@/store/AuthContext'
import MetricCard from '@/components/ui/MetricCard'
import Button from '@/components/ui/Button'
import { clsx } from 'clsx'

// ── Mock / demo data for sessions without real metrics ────────────
// Shown when no session exists yet (empty state onboarding)
const DEMO_METRICS = {
  prime_cost_pct:        { value: '61.4', unit: null, suffix: '%', trend: -3.2, trendLabel: 'vs last month', sufficiency: 'complete', insight: 'Below the 65% threshold — healthy prime cost.' },
  net_revenue:           { value: '₹4.2L', unit: null, suffix: null, trend: 8.1, trendLabel: 'vs last month', sufficiency: 'complete' },
  swiggy_net_payout:     { value: '₹1.84L', unit: null, suffix: null, trend: -1.2, trendLabel: 'vs last month', sufficiency: 'complete' },
  zomato_net_payout:     { value: '₹1.12L', unit: null, suffix: null, trend: 5.4, trendLabel: 'vs last month', sufficiency: 'complete' },
  penalty_total:         { value: '₹8,240', unit: null, suffix: null, trend: -12.3, trendLabel: 'vs last month', sufficiency: 'complete', insight: 'Down ₹1,200 from last month.' },
  cogs_pct:              { value: '34.2', unit: null, suffix: '%', trend: 1.1, trendLabel: 'vs last month', sufficiency: 'estimated', insight: 'Tally data missing — using fallback 35% estimate.' },
  labor_cost_pct:        { value: '27.2', unit: null, suffix: '%', trend: -2.4, trendLabel: 'vs last month', sufficiency: 'complete' },
  inventory_variance_pct:{ value: null, unit: null, suffix: '%', sufficiency: 'locked' },
}

const METRIC_LABELS = {
  prime_cost_pct:         'Prime Cost %',
  net_revenue:            'Net Revenue',
  swiggy_net_payout:      'Swiggy Net Payout',
  zomato_net_payout:      'Zomato Net Payout',
  penalty_total:          'Penalties',
  cogs_pct:               'COGS %',
  labor_cost_pct:         'Labor Cost %',
  inventory_variance_pct: 'Inventory Variance %',
}

// Mock revenue trend for chart
const REVENUE_TREND = [
  { day: 'Mon', revenue: 18200, target: 20000 },
  { day: 'Tue', revenue: 22400, target: 20000 },
  { day: 'Wed', revenue: 19800, target: 20000 },
  { day: 'Thu', revenue: 24100, target: 20000 },
  { day: 'Fri', revenue: 28600, target: 20000 },
  { day: 'Sat', revenue: 34200, target: 20000 },
  { day: 'Sun', revenue: 31500, target: 20000 },
]

// ── Custom chart tooltip ──────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="card p-3 text-xs font-body min-w-[120px]">
      <p className="text-[var(--text-muted)] mb-1">{label}</p>
      {payload.map(p => (
        <div key={p.dataKey} className="flex items-center justify-between gap-3">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-semibold text-[var(--text-primary)]">
            ₹{p.value.toLocaleString('en-IN')}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Status pill ───────────────────────────────────────────────────
function StatusPill({ status }) {
  const config = {
    done:    { icon: CheckCircle, text: 'Computed',  cls: 'text-emerald-400 bg-emerald-400/10' },
    running: { icon: RefreshCw,   text: 'Running…',  cls: 'text-saffron-400 bg-saffron-400/10 animate-pulse' },
    failed:  { icon: AlertCircle, text: 'Failed',    cls: 'text-red-400 bg-red-400/10' },
    queued:  { icon: Clock,       text: 'Queued',    cls: 'text-blue-400 bg-blue-400/10' },
    idle:    { icon: Clock,       text: 'Pending',   cls: 'text-[var(--text-muted)] bg-[var(--bg-subtle)]' },
  }[status] || { icon: Clock, text: status, cls: 'text-[var(--text-muted)] bg-[var(--bg-subtle)]' }

  const Icon = config.icon
  return (
    <span className={clsx('flex items-center gap-1.5 text-xs font-body font-medium px-2.5 py-1 rounded-full', config.cls)}>
      <Icon size={11} />
      {config.text}
    </span>
  )
}

// ── Empty state ───────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-saffron-500/10 border border-saffron-500/20 flex items-center justify-center mb-5">
        <FileText size={28} className="text-saffron-500" />
      </div>
      <h3 className="text-lg font-display font-semibold text-[var(--text-primary)] mb-2">
        No data yet
      </h3>
      <p className="text-sm text-[var(--text-secondary)] font-body max-w-xs mb-6 leading-relaxed">
        Upload your Swiggy, Zomato, or Tally exports to get restaurant-grade analytics
      </p>
      <Link to="/upload">
        <Button icon={<Upload size={16} />} size="lg">
          Upload your first file
        </Button>
      </Link>
    </div>
  )
}

export default function DashboardPage() {
  const { outletId } = useAuth()
  const navigate     = useNavigate()

  // For demo purposes: show demo data always.
  // In production: load real sessions and metrics from API.
  const [sessionId]   = useState('demo')        // would come from API in production
  const [metrics]     = useState(DEMO_METRICS)
  const [hasData]     = useState(true)           // flip to false to see empty state
  const [computeStatus] = useState('done')

  const now = new Date()
  const dateRange = `1 Mar – 31 Mar ${now.getFullYear()}`

  return (
    <div className="p-6 md:p-8 max-w-[1400px] mx-auto">

      {/* ── Page header ──────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap animate-fade-in">
        <div>
          <h1 className="text-2xl font-display font-bold text-[var(--text-primary)]">
            Dashboard
          </h1>
          <p className="text-sm text-[var(--text-secondary)] font-body mt-0.5">
            Main Outlet — Koregaon Park &nbsp;·&nbsp;
            <span className="text-[var(--text-muted)]">{dateRange}</span>
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <StatusPill status={computeStatus} />
          <Link to="/upload">
            <Button variant="secondary" icon={<Upload size={15} />} size="sm">
              New upload
            </Button>
          </Link>
        </div>
      </div>

      {!hasData ? (
        <EmptyState />
      ) : (
        <>
          {/* ── KPI summary row ──────────────────────────────── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {['prime_cost_pct', 'net_revenue', 'penalty_total', 'labor_cost_pct'].map((key, i) => {
              const m = metrics[key]
              return (
                <MetricCard
                  key={key}
                  label={METRIC_LABELS[key]}
                  value={m.value}
                  unit={m.unit}
                  suffix={m.suffix}
                  trend={m.trend}
                  trendLabel={m.trendLabel}
                  sufficiency={m.sufficiency}
                  insight={m.insight}
                  style={{ animationDelay: `${i * 60}ms` }}
                  onClick={() => navigate(`/metrics/demo`)}
                />
              )
            })}
          </div>

          {/* ── Revenue trend chart ──────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
            {/* Chart — 2/3 width */}
            <div className="lg:col-span-2 card p-5 animate-slide-up" style={{ animationDelay: '120ms' }}>
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="text-sm font-display font-semibold text-[var(--text-primary)]">
                    Daily Revenue
                  </h3>
                  <p className="text-xs text-[var(--text-muted)] font-body mt-0.5">
                    This week vs daily target
                  </p>
                </div>
                <div className="flex items-center gap-3 text-xs font-body">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-saffron-500" />
                    Revenue
                  </span>
                  <span className="flex items-center gap-1.5 text-[var(--text-muted)]">
                    <span className="w-2.5 h-2.5 rounded-full border border-[var(--border-strong)]" />
                    Target
                  </span>
                </div>
              </div>

              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={REVENUE_TREND} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="saffronGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f97d0a" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f97d0a" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="targetGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#6b6659" stopOpacity={0.1} />
                      <stop offset="95%" stopColor="#6b6659" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'DM Sans' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'DM Sans' }} axisLine={false} tickLine={false}
                    tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
                  <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'var(--saffron)', strokeWidth: 1, strokeDasharray: '4 2' }} />
                  <Area type="monotone" dataKey="target" name="Target" stroke="var(--border-strong)" strokeWidth={1.5} fill="url(#targetGrad)" strokeDasharray="4 2" dot={false} />
                  <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#f97d0a" strokeWidth={2.5} fill="url(#saffronGrad)" dot={false}
                    activeDot={{ r: 5, fill: '#f97d0a', stroke: 'var(--bg-elevated)', strokeWidth: 2 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Channel breakdown — 1/3 width */}
            <div className="card p-5 flex flex-col animate-slide-up" style={{ animationDelay: '160ms' }}>
              <h3 className="text-sm font-display font-semibold text-[var(--text-primary)] mb-4">
                Revenue by Channel
              </h3>
              <div className="flex-1 flex flex-col justify-center gap-4">
                {[
                  { label: 'Swiggy',   value: 43.8, color: '#f97d0a', amount: '₹1.84L' },
                  { label: 'Zomato',   value: 26.7, color: '#fb923c', amount: '₹1.12L' },
                  { label: 'Dine-in',  value: 22.1, color: '#fbbf24', amount: '₹0.93L' },
                  { label: 'Takeaway', value: 7.4,  color: '#9c9584', amount: '₹0.31L' },
                ].map(({ label, value, color, amount }) => (
                  <div key={label}>
                    <div className="flex justify-between text-xs font-body mb-1.5">
                      <span className="text-[var(--text-secondary)]">{label}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[var(--text-muted)]">{amount}</span>
                        <span className="font-semibold" style={{ color }}>{value}%</span>
                      </div>
                    </div>
                    <div className="h-1.5 bg-[var(--bg-subtle)] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${value}%`, background: color }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Remaining metric cards ────────────────────────── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {['swiggy_net_payout', 'zomato_net_payout', 'cogs_pct', 'inventory_variance_pct'].map((key, i) => {
              const m = metrics[key]
              return (
                <MetricCard
                  key={key}
                  label={METRIC_LABELS[key]}
                  value={m.value}
                  unit={m.unit}
                  suffix={m.suffix}
                  trend={m.trend}
                  trendLabel={m.trendLabel}
                  sufficiency={m.sufficiency}
                  insight={m.insight}
                  style={{ animationDelay: `${(i + 4) * 60}ms` }}
                  onClick={() => navigate('/metrics/demo')}
                />
              )
            })}
          </div>

          {/* ── View full metrics CTA ─────────────────────────── */}
          <div className="card card-interactive p-4 flex items-center justify-between gap-4 animate-fade-in">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-saffron-500/10 border border-saffron-500/20 flex items-center justify-center">
                <Zap size={16} className="text-saffron-500" />
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--text-primary)] font-body">
                  View full analytics report
                </p>
                <p className="text-xs text-[var(--text-muted)] font-body">
                  Insights, actions, and dispute templates
                </p>
              </div>
            </div>
            <Link to="/metrics/demo">
              <Button variant="secondary" size="sm" icon={<ChevronRight size={14} />}>
                Open report
              </Button>
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
