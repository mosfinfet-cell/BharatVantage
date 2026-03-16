/**
 * DashboardPage.jsx — v2
 *
 * Shows real upload sessions from the API.
 * Navigates to /metrics/:sessionId for computed sessions.
 * Shows upload CTA when no sessions exist.
 */
import React, { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Upload, RefreshCw, ArrowRight, CheckCircle,
  Clock, AlertCircle, ChevronRight, Zap
} from 'lucide-react'
import { compute as computeApi, upload as uploadApi } from '@/lib/api'
import { useAuth } from '@/store/AuthContext'

// ── Status badge ──────────────────────────────────────────────────
function StatusBadge({ status }) {
  const cfg = {
    done:      { label: 'Ready',      cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', icon: CheckCircle },
    queued:    { label: 'Queued',     cls: 'bg-blue-500/10    text-blue-400    border-blue-500/20',    icon: Clock },
    running:   { label: 'Computing',  cls: 'bg-amber-500/10   text-amber-400   border-amber-500/20',   icon: RefreshCw },
    ingesting: { label: 'Ingesting',  cls: 'bg-blue-500/10    text-blue-400    border-blue-500/20',    icon: RefreshCw },
    failed:    { label: 'Failed',     cls: 'bg-red-500/10     text-red-400     border-red-500/20',     icon: AlertCircle },
    pending:   { label: 'Pending',    cls: 'bg-zinc-700/30    text-zinc-400    border-zinc-600/30',    icon: Clock },
  }[status] || { label: status, cls: 'bg-zinc-700/30 text-zinc-400 border-zinc-600/30', icon: Clock }
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${cfg.cls}`}>
      <Icon size={11} />
      {cfg.label}
    </span>
  )
}

// ── Empty state ───────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-6 text-center">
      <div className="w-16 h-16 rounded-2xl bg-[var(--saffron-subtle)] flex items-center justify-center">
        <Upload size={28} className="text-[var(--saffron)]" />
      </div>
      <div>
        <h2 className="text-xl font-bold font-display mb-2">No data uploaded yet</h2>
        <p className="text-sm text-[var(--text-secondary)] max-w-sm">
          Upload your Swiggy, Zomato, Petpooja, or Tally files to see your restaurant analytics.
        </p>
      </div>
      <Link to="/upload"
        className="flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm
          bg-[var(--saffron)] text-[var(--bg-base)] hover:opacity-90 transition-opacity">
        Upload your first file
        <ArrowRight size={15} />
      </Link>
    </div>
  )
}

// ── Session card ──────────────────────────────────────────────────
function SessionCard({ session, onCompute, computing }) {
  const navigate = useNavigate()
  const isReady    = session.compute_status === 'done'
  const isFailed   = session.compute_status === 'failed' || session.ingest_status === 'failed'
  const isRunning  = ['queued','running','ingesting'].includes(session.compute_status) ||
                     ['queued','running'].includes(session.ingest_status)

  const sources = session.sources_present || []
  const dateFrom = session.date_from ? new Date(session.date_from).toLocaleDateString('en-IN', { day:'numeric', month:'short' }) : '—'
  const dateTo   = session.date_to   ? new Date(session.date_to).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' }) : '—'

  return (
    <div className="card p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <StatusBadge status={isReady ? 'done' : isFailed ? 'failed' : isRunning ? session.compute_status || 'queued' : 'pending'} />
            {sources.length > 0 && (
              <div className="flex gap-1">
                {sources.map(s => (
                  <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border)] capitalize">
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            {dateFrom} → {dateTo}
          </p>
        </div>
        <span className="text-[10px] text-[var(--text-muted)] shrink-0">
          {new Date(session.created_at || Date.now()).toLocaleDateString('en-IN')}
        </span>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {isReady && (
          <button
            onClick={() => navigate(`/metrics/${session.id}`)}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl
              bg-[var(--saffron)] text-[var(--bg-base)] font-semibold text-sm
              hover:opacity-90 transition-opacity">
            View Analytics
            <ChevronRight size={14} />
          </button>
        )}

        {!isReady && !isFailed && !isRunning && session.ingest_status === 'done' && (
          <button
            onClick={() => onCompute(session.id)}
            disabled={computing === session.id}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl
              bg-blue-500/10 text-blue-400 border border-blue-500/20 font-semibold text-sm
              hover:bg-blue-500/20 transition-colors disabled:opacity-50">
            {computing === session.id ? <RefreshCw size={14} className="animate-spin" /> : <Zap size={14} />}
            {computing === session.id ? 'Computing…' : 'Compute Metrics'}
          </button>
        )}

        {isRunning && (
          <div className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl
            bg-amber-500/10 text-amber-400 border border-amber-500/20 text-sm font-semibold">
            <RefreshCw size={14} className="animate-spin" />
            Processing…
          </div>
        )}

        {isFailed && (
          <div className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl
            bg-red-500/10 text-red-400 border border-red-500/20 text-sm">
            <AlertCircle size={14} />
            Processing failed — try re-uploading
          </div>
        )}

        <Link to="/upload"
          className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl
            border border-[var(--border)] text-[var(--text-secondary)] text-sm
            hover:text-[var(--text-primary)] hover:border-[var(--border-hover)] transition-colors">
          <Upload size={13} />
          New
        </Link>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────
export default function DashboardPage() {
  const { token, outletId } = useAuth()
  const navigate = useNavigate()
  const [sessions,  setSessions]  = useState([])
  const [loading,   setLoading]   = useState(true)
  const [computing, setComputing] = useState(null)
  const [error,     setError]     = useState(null)

  const loadSessions = useCallback(async () => {
    if (!token || !outletId) return
    try {
      // Use the upload list endpoint — GET /upload/sessions
      const res = await fetch(
        `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}/upload/sessions`,
        { headers: { Authorization: `Bearer ${token}`, 'X-Outlet-ID': outletId } }
      )
      if (res.ok) {
        const data = await res.json()
        // Sort by created_at desc
        const sorted = (Array.isArray(data) ? data : data.sessions || [])
          .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
        setSessions(sorted)
      } else if (res.status === 404) {
        // Endpoint may not exist yet — show empty state
        setSessions([])
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [token, outletId])

  useEffect(() => {
    loadSessions()
    // Poll every 5s if any session is in-progress
    const interval = setInterval(() => {
      if (sessions.some(s =>
        ['queued','running','ingesting'].includes(s.compute_status) ||
        ['queued','running'].includes(s.ingest_status)
      )) {
        loadSessions()
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [loadSessions, sessions])

  async function handleCompute(sessionId) {
    setComputing(sessionId)
    try {
      await computeApi.enqueue(token, outletId, sessionId)
      await loadSessions()
    } catch (e) {
      alert('Compute failed: ' + e.message)
    } finally {
      setComputing(null)
    }
  }

  // If there's exactly one ready session, auto-navigate to its metrics
  useEffect(() => {
    const ready = sessions.filter(s => s.compute_status === 'done')
    if (ready.length === 1 && sessions.length === 1) {
      navigate(`/metrics/${ready[0].id}`, { replace: true })
    }
  }, [sessions, navigate])

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-display">Dashboard</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Your restaurant analytics sessions
          </p>
        </div>
        <Link to="/upload"
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm
            bg-[var(--saffron)] text-[var(--bg-base)] hover:opacity-90 transition-opacity">
          <Upload size={14} />
          Upload data
        </Link>
      </div>

      {/* Content */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <RefreshCw className="animate-spin text-[var(--saffron)]" size={24} />
        </div>
      )}

      {!loading && sessions.length === 0 && <EmptyState />}

      {!loading && sessions.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider font-semibold">
            {sessions.length} session{sessions.length !== 1 ? 's' : ''}
          </p>
          {sessions.map(s => (
            <SessionCard
              key={s.id}
              session={s}
              onCompute={handleCompute}
              computing={computing}
            />
          ))}
        </div>
      )}

      {error && (
        <div className="card p-4 border border-red-500/20 bg-red-500/5 text-sm text-red-400">
          Error loading sessions: {error}
        </div>
      )}
    </div>
  )
}
