// components/ui/MetricCard.jsx
//
// Reasoning: The metric card is the most important UI element.
// It has 3 states driven by MetricSufficiency from the backend:
//   complete  → full value shown, green badge
//   estimated → value shown with ⚠ indicator, saffron badge
//   locked    → blurred/greyed with lock icon, grey badge
//
// This mirrors exactly what backend returns in metric_snapshots.sufficiency

import React from 'react'
import { clsx } from 'clsx'
import { Lock, TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react'

const sufficiencyConfig = {
  complete:  { badge: 'badge-complete',  label: 'Complete' },
  estimated: { badge: 'badge-estimated', label: 'Estimated' },
  locked:    { badge: 'badge-locked',    label: 'Locked' },
  manual:    { badge: 'badge-estimated', label: 'Manual' },
}

function TrendIcon({ trend }) {
  if (trend > 0)  return <TrendingUp  size={14} className="text-emerald-400" />
  if (trend < 0)  return <TrendingDown size={14} className="text-red-400" />
  return <Minus size={14} className="text-[var(--text-muted)]" />
}

export default function MetricCard({
  label,
  value,
  unit,
  suffix,
  trend,
  trendLabel,
  sufficiency = 'complete',
  insight,
  className,
  onClick,
  style,
}) {
  const config  = sufficiencyConfig[sufficiency] || sufficiencyConfig.complete
  const isLocked = sufficiency === 'locked'

  return (
    <div
      onClick={onClick}
      className={clsx(
        'card card-interactive p-5 flex flex-col gap-3 relative overflow-hidden',
        'animate-slide-up',
        onClick && 'cursor-pointer',
        isLocked && 'opacity-60',
        className
      )}
      style={style}
    >
      {/* Subtle geometric top accent */}
      {!isLocked && sufficiency === 'complete' && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-saffron-500/60 to-transparent rounded-t-[var(--radius-card)]" />
      )}

      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-[var(--text-secondary)] font-body leading-tight">
          {label}
        </span>
        <span className={clsx(
          'flex-shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full font-body',
          config.badge
        )}>
          {config.label}
        </span>
      </div>

      {/* Value */}
      <div className="flex items-end gap-1.5">
        {isLocked ? (
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <Lock size={18} />
            <span className="text-sm font-body">Insufficient data</span>
          </div>
        ) : (
          <>
            {unit && (
              <span className="text-lg font-medium text-[var(--text-secondary)] font-body mb-0.5">
                {unit}
              </span>
            )}
            <span className={clsx(
              'text-3xl font-bold font-display leading-none',
              sufficiency === 'estimated' && 'text-saffron-500',
              sufficiency === 'complete'  && 'text-[var(--text-primary)]',
            )}>
              {value ?? '—'}
            </span>
            {suffix && (
              <span className="text-lg font-medium text-[var(--text-secondary)] font-body mb-0.5">
                {suffix}
              </span>
            )}
            {sufficiency === 'estimated' && (
              <AlertTriangle size={14} className="text-saffron-400 mb-1 flex-shrink-0" />
            )}
          </>
        )}
      </div>

      {/* Trend */}
      {!isLocked && trend !== undefined && (
        <div className="flex items-center gap-1.5">
          <TrendIcon trend={trend} />
          <span className={clsx(
            'text-xs font-body font-medium',
            trend > 0 ? 'text-emerald-400' :
            trend < 0 ? 'text-red-400' :
            'text-[var(--text-muted)]'
          )}>
            {trend > 0 ? '+' : ''}{trend}%
          </span>
          {trendLabel && (
            <span className="text-xs text-[var(--text-muted)] font-body">{trendLabel}</span>
          )}
        </div>
      )}

      {/* Insight text */}
      {!isLocked && insight && (
        <p className="text-xs text-[var(--text-muted)] font-body leading-relaxed border-t border-[var(--border)] pt-2">
          {insight}
        </p>
      )}
    </div>
  )
}
