// pages/MetricsPage.jsx
//
// Reasoning: This page:
// 1. Polls GET /status/:sessionId until compute_status = done
// 2. Calls GET /metrics/:sessionId to load MetricSnapshot
// 3. Renders all restaurant metrics with sufficiency badges
// 4. Shows insights and action buttons (raise dispute, flag shift, export)

import React, { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  RefreshCw, AlertTriangle, CheckCircle, FileDown,
  MessageSquare, Flag, ChevronDown, ChevronUp,
  ArrowLeft, Zap, Clock
} from 'lucide-react'
import { compute as computeApi } from '@/lib/api'
import MetricCard from '@/components/ui/MetricCard'
import Button from '@/components/ui/Button'
import { clsx } from 'clsx'

const POLL_INTERVAL = 3000  // 3s between status polls

// ── Demo metrics — mirrors RestaurantMetricResult schema ──────────
const DEMO_SNAPSHOT = {
  vertical: 'restaurant',
  computed_at: new Date().toISOString(),
  date_from: '2024-03-01',
  date_to:   '2024-03-31',
  sources_used: ['swiggy', 'zomato', 'petpooja'],
  alignment_warnings: [],
  result: {
    net_revenue:            { value: 420000,  label: 'Net Revenue',           unit: '₹', suffix: null  },
    gross_revenue:          { value: 468000,  label: 'Gross Revenue',          unit: '₹', suffix: null  },
    prime_cost_pct:         { value: 61.4,    label: 'Prime Cost %',           unit: null, suffix: '%' },
    cogs_pct:               { value: 34.2,    label: 'COGS %',                 unit: null, suffix: '%' },
    labor_cost_pct:         { value: 27.2,    label: 'Labor Cost %',           unit: null, suffix: '%' },
    swiggy_net_payout:      { value: 184000,  label: 'Swiggy Net Payout',      unit: '₹', suffix: null  },
    zomato_net_payout:      { value: 112000,  label: 'Zomato Net Payout',      unit: '₹', suffix: null  },
    commission_total:       { value: 72800,   label: 'Total Commission',        unit: '₹', suffix: null  },
    penalty_total:          { value: 8240,    label: 'Penalties',               unit: '₹', suffix: null  },
    ad_spend_total:         { value: 18500,   label: 'Ad Spend',               unit: '₹', suffix: null  },
    inventory_variance_pct: { value: null,    label: 'Inventory Variance %',   unit: null, suffix: '%' },
    revpash:                { value: 485,     label: 'RevPASH',                unit: '₹', suffix: null  },
  },
  sufficiency: {
    net_revenue:            'complete',
    gross_revenue:          'complete',
    prime_cost_pct:         'complete',
    cogs_pct:               'estimated',
    labor_cost_pct:         'complete',
    swiggy_net_payout:      'complete',
    zomato_net_payout:      'complete',
    commission_total:       'complete',
    penalty_total:          'complete',
    ad_spend_total:         'complete',
    inventory_variance_pct: 'locked',
    revpash:                'complete',
  }
}

const DEMO_INSIGHTS = [
  { type: 'warn', icon: '⚠', title: 'Prime Cost approaching threshold', body: 'At 61.4%, you\'re within 3.6% of the 65% danger zone. Consider reviewing labor scheduling this week.', action: 'flag_shift' },
  { type: 'good', icon: '↓', title: 'Penalties down ₹1,200 vs last month', body: 'Dispute rate has improved. 3 orders still pending reversal from Swiggy.', action: 'raise_dispute' },
  { type: 'info', icon: 'ℹ', title: 'COGS data is estimated', body: 'We used a 35% fallback since no Tally/vendor data was uploaded. Upload purchase records for exact COGS.', action: null },
]

// ── Insight card ──────────────────────────────────────────────────
function InsightCard({ insight, onAction }) {
  const typeConfig = {
    good: { border: 'border-emerald-500/20', icon: 'text-emerald-400', bg: 'bg-emerald-500/5' },
    warn: { border: 'border-saffron-500/20', icon: 'text-saffron-400', bg: 'bg-saffron-500/5' },
    info: { border: 'border-blue-500/20',    icon: 'text-blue-400',    bg: 'bg-blue-500/5' },
  }[insight.type] || { border: 'border-[var(--border)]', icon: 'text-[var(--text-muted)]', bg: '' }

  return (
    <div className={clsx('card p-4 border', typeConfig.border, typeConfig.bg, 'animate-slide-up')}>
      <div className="flex items-start gap-3">
        <span className={clsx('text-base flex-shrink-0 mt-0.5', typeConfig.icon)}>{insight.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold font-body text-[var(--text-primary)]">{insight.title}</p>
          <p className="text-xs text-[var(--text-secondary)] font-body mt-0.5 leading-relaxed">{insight.body}</p>
          {insight.action && (
            <button
              onClick={() => onAction(insight.action)}
              className="mt-2 text-xs font-semibold text-saffron-500 hover:text-saffron-400 font-body transition-colors"
            >
              {insight.action === 'raise_dispute'  ? 'Generate dispute template →' :
               insight.action === 'flag_shift'     ? 'Review shift report →' : 'Take action →'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Action result modal ───────────────────────────────────────────
function ActionModal({ result, type, onClose }) {
  if (!result) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 animate-fade-in">
      <div className="card w-full max-w-md p-6 animate-slide-up">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-saffron-500/15 flex items-center justify-center">
              {type === 'raise_dispute' ? <MessageSquare size={14} className="text-saffron-500" /> :
               <Flag size={14} className="text-saffron-500" />}
            </div>
            <h3 className="font-display font-semibold text-[var(--text-primary)] text-sm">
              {type === 'raise_dispute' ? 'Dispute Template' : 'Shift Flag Alert'}
            </h3>
          </div>
          <button onClick={onClose} className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1">✕</button>
        </div>

        {result.email_template ? (
          <div className="bg-[var(--bg-subtle)] border border-[var(--border)] rounded-xl p-4">
            <pre className="text-xs font-mono text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed overflow-auto max-h-64">
              {result.email_template}
            </pre>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm font-body text-[var(--text-primary)] font-medium">{result.message}</p>
            {result.action_items?.map((item, i) => (
              <div key={i} className="flex items-center gap-2 text-sm text-[var(--text-secondary)] font-body">
                <div className="w-1.5 h-1.5 rounded-full bg-saffron-500 flex-shrink-0" />
                {item}
              </div>
            ))}
          </div>
        )}

        <Button
          variant="secondary" size="sm" className="w-full mt-4"
          onClick={onClose}
        >
          Close
        </Button>
      </div>
    </div>
  )
}

export default function MetricsPage() {
  const { sessionId } = useParams()
  const isDemoSession = sessionId?.startsWith('demo')

  const [status,    setStatus]    = useState(isDemoSession ? 'done' : 'running')
  const [snapshot,  setSnapshot]  = useState(isDemoSession ? DEMO_SNAPSHOT : null)
  const [loading,   setLoading]   = useState(!isDemoSession)
  const [error,     setError]     = useState('')
  const [modal,     setModal]     = useState(null)  // { type, result }
  const [expanded,  setExpanded]  = useState({})
  const [acting,    setActing]    = useState(false)

  // Poll status until done (skipped for demo sessions)
  useEffect(() => {
    if (isDemoSession || status === 'done' || status === 'failed') return

    const poll = setInterval(async () => {
      try {
        const data = await computeApi.getStatus(sessionId)
        setStatus(data.compute_status)
        if (data.compute_status === 'done') {
          clearInterval(poll)
          loadMetrics()
        }
      } catch (err) {
        setError('Failed to poll status')
        clearInterval(poll)
      }
    }, POLL_INTERVAL)

    return () => clearInterval(poll)
  }, [sessionId, status, isDemoSession])

  const loadMetrics = useCallback(async () => {
    if (isDemoSession) return
    setLoading(true)
    try {
      const data = await computeApi.getMetrics(sessionId)
      setSnapshot(data)
    } catch (err) {
      setError(err.message || 'Failed to load metrics')
    } finally {
      setLoading(false)
    }
  }, [sessionId, isDemoSession])

  const handleAction = async (actionType) => {
    // For demo: show mock result immediately
    if (isDemoSession) {
      const mockResult = actionType === 'raise_dispute'
        ? {
            email_template: `Subject: Penalty Dispute Request — Restaurant Partner\n\nDear Swiggy Partner Support Team,\n\nI am writing to formally dispute penalties totalling ₹8,240 charged to my account.\n\nOrder #4521 | Date: 15 Mar 2024 | Amount: ₹1,240\nOrder #4489 | Date: 12 Mar 2024 | Amount: ₹980\nOrder #4341 | Date: 08 Mar 2024 | Amount: ₹6,020\n\nI request a detailed review and reversal of these charges.\n\nPlease respond within 7 business days.\n\nRegards,\n[Restaurant Name]\n[Partner ID]`,
            total_disputed: 8240,
          }
        : {
            alert_type: 'high_prime_cost',
            message: 'Prime Cost at 61.4% — approaching 65% threshold.',
            action_items: [
              'Audit overtime hours this period',
              'Review portion sizes for high-cost items',
              'Compare theoretical vs actual ingredient depletion',
            ]
          }
      setModal({ type: actionType, result: mockResult })
      return
    }
  }

  // Group metrics by category for display
  const metricsGroups = snapshot ? [
    {
      label: 'Revenue',
      keys: ['net_revenue', 'gross_revenue', 'revpash']
    },
    {
      label: 'Platform Payouts',
      keys: ['swiggy_net_payout', 'zomato_net_payout', 'commission_total', 'penalty_total', 'ad_spend_total']
    },
    {
      label: 'Cost Analysis',
      keys: ['prime_cost_pct', 'cogs_pct', 'labor_cost_pct', 'inventory_variance_pct']
    },
  ] : []

  const formatValue = (key, raw) => {
    if (raw === null || raw === undefined) return null
    if (key.endsWith('_pct'))    return raw.toFixed(1)
    if (key.startsWith('revpash')) return raw.toLocaleString('en-IN')
    return `${(raw / 1000).toFixed(0)}k`
  }

  // ── Loading / polling state ───────────────────────────────────
  if (status !== 'done' || loading) {
    return (
      <div className="p-8 max-w-[900px] mx-auto">
        <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-8 transition-colors font-body">
          <ArrowLeft size={14} /> Dashboard
        </Link>
        <div className="flex flex-col items-center justify-center py-24 gap-5">
          <div className="w-16 h-16 rounded-2xl bg-saffron-500/10 border border-saffron-500/20 flex items-center justify-center animate-glow-pulse">
            {status === 'running' || status === 'queued'
              ? <RefreshCw size={26} className="text-saffron-500 animate-spin" />
              : <Clock size={26} className="text-saffron-500" />
            }
          </div>
          <div className="text-center">
            <p className="text-lg font-display font-semibold text-[var(--text-primary)]">
              {status === 'running' ? 'Computing metrics…' :
               status === 'queued'  ? 'In queue…' :
               'Loading metrics…'}
            </p>
            <p className="text-sm text-[var(--text-secondary)] font-body mt-1">
              This usually takes 10–30 seconds
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8 max-w-[900px] mx-auto">
        <div className="card p-6 flex items-center gap-3 text-red-400">
          <AlertTriangle size={20} />
          <p className="font-body">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 md:p-8 max-w-[1100px] mx-auto">

      {/* Header */}
      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap animate-fade-in">
        <div>
          <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-xs text-[var(--text-muted)] hover:text-saffron-500 mb-2 transition-colors font-body">
            <ArrowLeft size={12} /> Dashboard
          </Link>
          <h1 className="text-2xl font-display font-bold text-[var(--text-primary)]">
            Analytics Report
          </h1>
          <p className="text-sm text-[var(--text-secondary)] font-body mt-0.5">
            {snapshot?.date_from} → {snapshot?.date_to} &nbsp;·&nbsp;
            Sources: {snapshot?.sources_used?.join(', ')}
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <Button
            variant="secondary" size="sm"
            icon={<MessageSquare size={14} />}
            onClick={() => handleAction('raise_dispute')}
            loading={acting}
          >
            Raise dispute
          </Button>
          <Button
            variant="secondary" size="sm"
            icon={<Flag size={14} />}
            onClick={() => handleAction('flag_shift')}
          >
            Flag shift
          </Button>
          <Button
            variant="ghost" size="sm"
            icon={<FileDown size={14} />}
            onClick={() => handleAction('export_report')}
          >
            Export
          </Button>
        </div>
      </div>

      {/* Alerts from alignment warnings */}
      {snapshot?.alignment_warnings?.length > 0 && (
        <div className="card border-saffron-500/20 bg-saffron-500/5 p-4 mb-6 flex items-start gap-3 animate-slide-up">
          <AlertTriangle size={16} className="text-saffron-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-[var(--text-primary)] font-body">Data alignment warnings</p>
            {snapshot.alignment_warnings.map((w, i) => (
              <p key={i} className="text-xs text-[var(--text-secondary)] font-body mt-1">{w}</p>
            ))}
          </div>
        </div>
      )}

      {/* Insights */}
      {DEMO_INSIGHTS.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-display font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">
            Key Insights
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {DEMO_INSIGHTS.map((insight, i) => (
              <InsightCard key={i} insight={insight} onAction={handleAction} />
            ))}
          </div>
        </div>
      )}

      {/* Metric groups */}
      {metricsGroups.map((group, gi) => (
        <div key={group.label} className="mb-8">
          <h2 className="text-sm font-display font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">
            {group.label}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {group.keys.map((key, i) => {
              const meta  = snapshot.result?.[key]
              const suf   = snapshot.sufficiency?.[key] || 'locked'
              const raw   = meta?.value
              return (
                <MetricCard
                  key={key}
                  label={meta?.label || key}
                  value={raw !== null && raw !== undefined ? formatValue(key, raw) : null}
                  unit={meta?.unit}
                  suffix={meta?.suffix}
                  sufficiency={suf}
                  style={{ animationDelay: `${(gi * 4 + i) * 40}ms` }}
                />
              )
            })}
          </div>
        </div>
      ))}

      {/* Action modal */}
      {modal && (
        <ActionModal
          type={modal.type}
          result={modal.result}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  )
}
