// pages/UploadPage.jsx
//
// Reasoning: Upload flow matches the backend exactly:
// 1. POST /upload (multipart) → returns session_id + file detections
// 2. If needs_confirm → show confirmation UI for each file
// 3. PATCH /upload/:sessionId/confirm → confirms source types
// 4. POST /compute/:sessionId → triggers background compute
// 5. Navigate to /metrics/:sessionId to poll status

import React, { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload, File, CheckCircle, AlertTriangle, X,
  ChevronRight, Loader2, FileText, Zap
} from 'lucide-react'
import { upload as uploadApi, compute as computeApi, tokenStore } from '@/lib/api'
import Button from '@/components/ui/Button'
import { clsx } from 'clsx'

// Source types recognised by backend
const SOURCE_OPTIONS = [
  { value: 'swiggy',       label: 'Swiggy Export' },
  { value: 'zomato',       label: 'Zomato Export' },
  { value: 'petpooja',     label: 'Petpooja (POS)' },
  { value: 'tally',        label: 'Tally Vouchers' },
  { value: 'excel_payroll',label: 'Payroll Sheet' },
  { value: 'generic',      label: 'Generic / Other' },
]

const CONFIDENCE_THRESHOLDS = {
  high:   0.85,
  medium: 0.6,
}

function getConfidenceLabel(confidence) {
  if (confidence >= CONFIDENCE_THRESHOLDS.high)   return { label: 'High confidence', cls: 'badge-complete' }
  if (confidence >= CONFIDENCE_THRESHOLDS.medium) return { label: 'Review suggested', cls: 'badge-estimated' }
  return { label: 'Manual review', cls: 'badge-locked' }
}

// ── Step indicator ────────────────────────────────────────────────
function StepIndicator({ step }) {
  const steps = ['Upload Files', 'Confirm Sources', 'Processing']
  return (
    <div className="flex items-center gap-0">
      {steps.map((s, i) => (
        <React.Fragment key={s}>
          <div className="flex items-center gap-2">
            <div className={clsx(
              'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold font-display transition-all',
              step === i + 1 ? 'bg-saffron-500 text-white glow-saffron-sm' :
              step > i + 1  ? 'bg-saffron-500/20 text-saffron-400' :
              'bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border)]'
            )}>
              {step > i + 1 ? <CheckCircle size={14} /> : i + 1}
            </div>
            <span className={clsx(
              'text-sm font-body hidden sm:block',
              step === i + 1 ? 'text-[var(--text-primary)] font-medium' : 'text-[var(--text-muted)]'
            )}>
              {s}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className={clsx(
              'flex-1 h-px mx-3 min-w-[20px] transition-all',
              step > i + 1 ? 'bg-saffron-500/40' : 'bg-[var(--border)]'
            )} />
          )}
        </React.Fragment>
      ))}
    </div>
  )
}

// ── Drop zone ─────────────────────────────────────────────────────
function DropZone({ onFiles, disabled }) {
  const inputRef   = useRef()
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const files = Array.from(e.dataTransfer.files).filter(f =>
      /\.(csv|xlsx|xls)$/.test(f.name.toLowerCase())
    )
    if (files.length) onFiles(files)
  }, [onFiles])

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={clsx(
        'border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer',
        'transition-all duration-200',
        dragging
          ? 'drop-zone-active'
          : 'border-[var(--border-strong)] hover:border-saffron-500/40 hover:bg-saffron-500/3',
        disabled && 'opacity-40 cursor-not-allowed'
      )}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={e => onFiles(Array.from(e.target.files))}
        disabled={disabled}
      />

      <div className="flex flex-col items-center gap-4">
        <div className={clsx(
          'w-14 h-14 rounded-2xl border flex items-center justify-center transition-all',
          dragging
            ? 'bg-saffron-500/15 border-saffron-500/40'
            : 'bg-[var(--bg-subtle)] border-[var(--border)]'
        )}>
          <Upload size={24} className={dragging ? 'text-saffron-500' : 'text-[var(--text-muted)]'} />
        </div>

        <div>
          <p className="text-base font-display font-semibold text-[var(--text-primary)]">
            Drop files here, or{' '}
            <span className="text-saffron-500">browse</span>
          </p>
          <p className="text-sm text-[var(--text-muted)] font-body mt-1">
            CSV, XLSX — Swiggy, Zomato, Tally, Petpooja exports
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-center">
          {['Swiggy', 'Zomato', 'Petpooja', 'Tally'].map(s => (
            <span key={s} className="text-[11px] text-[var(--text-muted)] font-body px-2.5 py-1 bg-[var(--bg-subtle)] border border-[var(--border)] rounded-full">
              {s}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── File row ──────────────────────────────────────────────────────
function FileRow({ file, detection, confirmedSource, onSourceChange, onRemove }) {
  const needsConfirm = !detection || detection.confidence < CONFIDENCE_THRESHOLDS.high
  const conf = detection ? getConfidenceLabel(detection.confidence) : null

  return (
    <div className="card p-4 flex items-start gap-4 animate-slide-up">
      <div className="w-9 h-9 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border)] flex items-center justify-center flex-shrink-0">
        <FileText size={16} className="text-saffron-500" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-medium font-body text-[var(--text-primary)] truncate">
            {file.name}
          </p>
          <span className="text-xs text-[var(--text-muted)] font-body flex-shrink-0">
            {(file.size / 1024).toFixed(0)} KB
          </span>
          {conf && (
            <span className={clsx('text-[10px] font-semibold px-2 py-0.5 rounded-full font-body flex-shrink-0', conf.cls)}>
              {conf.label}
            </span>
          )}
        </div>

        {detection && (
          <p className="text-xs text-[var(--text-muted)] font-body mt-0.5">
            Detected: <span className="text-[var(--text-secondary)]">
              {SOURCE_OPTIONS.find(s => s.value === detection.detected_source)?.label || detection.detected_source}
            </span>
          </p>
        )}

        {/* Source selector — shown if low confidence or no detection */}
        {needsConfirm && (
          <div className="mt-2">
            <label className="text-xs text-[var(--text-muted)] font-body mb-1 block">
              Confirm source type
            </label>
            <select
              value={confirmedSource || detection?.detected_source || ''}
              onChange={e => onSourceChange(e.target.value)}
              className="text-xs font-body bg-[var(--bg-subtle)] border border-[var(--border)] rounded-lg px-3 py-1.5 text-[var(--text-primary)] input-saffron"
            >
              <option value="">Select source…</option>
              {SOURCE_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <button onClick={onRemove} className="flex-shrink-0 p-1.5 rounded-lg text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/8 transition-all">
        <X size={14} />
      </button>
    </div>
  )
}

export default function UploadPage() {
  const navigate = useNavigate()
  const [step, setStep]                 = useState(1)  // 1=upload 2=confirm 3=processing
  const [files, setFiles]               = useState([])
  const [uploading, setUploading]       = useState(false)
  const [sessionData, setSessionData]   = useState(null)
  const [confirmations, setConfirmations] = useState({})  // { filename: source_type }
  const [error, setError]               = useState('')
  const [ingestPolling, setIngestPolling] = useState(false)  // true while waiting for ARQ ingestion

  const addFiles = (newFiles) => {
    // Deduplicate by name
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name))
      return [...prev, ...newFiles.filter(f => !existing.has(f.name))]
    })
  }

  const removeFile = (name) => {
    setFiles(prev => prev.filter(f => f.name !== name))
  }

  // Step 1 → 2: Upload files to backend
  const handleUpload = async () => {
    if (!files.length) return
    setError('')
    setUploading(true)
    try {
      const token    = tokenStore.getToken()
      const outletId = tokenStore.getOutlet()
      // uploadFile now accepts an array — sends all files in one multipart request
      const data = await uploadApi.uploadFile(token, outletId, files)
      setSessionData(data)
      setStep(2)
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  // Step 2 → 3: Confirm sources + poll ingestion + trigger compute
  const handleConfirm = async () => {
    setError('')
    setUploading(true)
    try {
      const token    = tokenStore.getToken()
      const outletId = tokenStore.getOutlet()

      // Build confirmations array: [{ file_id, confirmed_source }]
      // file_id comes from sessionData.files[].file_id (backend UUID)
      // confirmed_source falls back to auto-detected source for high-confidence files.
      const confirmList = (sessionData?.files || []).map(f => ({
        file_id:          f.file_id,
        confirmed_source: confirmations[f.file_id] || confirmations[f.filename] || f.detected_source,
      }))

      // 1. Confirm source types (required even for high-confidence auto-detected files
      //    so the backend marks all files as confirmed before ingestion runs).
      await uploadApi.confirmSession(sessionData.session_id, confirmList)

      // 2. Poll ingest status until done — the backend rejects POST /compute
      //    with 400 "Ingestion not complete" if ingest_status !== "done".
      //    The ARQ worker processes the ingestion job asynchronously; we must
      //    wait for it here before calling compute.
      const MAX_POLLS = 60          // 60 × 2s = 2 minutes max wait
      const POLL_INTERVAL_MS = 2000
      let ingestDone = false
      setIngestPolling(true)

      for (let i = 0; i < MAX_POLLS; i++) {
        await new Promise(r => setTimeout(r, POLL_INTERVAL_MS))
        const status = await computeApi.getStatus(token, outletId, sessionData.session_id)

        if (status.ingest_status === 'done') {
          ingestDone = true
          break
        }
        if (status.ingest_status === 'failed') {
          throw new Error(status.error_message || 'Ingestion failed. Please re-upload the file.')
        }
        // Still pending/ingesting — keep polling
      }

      setIngestPolling(false)
      if (!ingestDone) {
        throw new Error('Ingestion is taking too long. Please check Railway logs and try again.')
      }

      // 3. Trigger compute job (ingestion is confirmed done)
      await computeApi.enqueue(token, outletId, sessionData.session_id)

      setStep(3)
      setTimeout(() => {
        navigate(`/metrics/${sessionData.session_id}`)
      }, 1500)
    } catch (err) {
      setError(err.message || 'Failed to start compute.')
    } finally {
      setUploading(false)
      setIngestPolling(false)
    }
  }

  // Demo mode: simulate backend response when no real session
  const handleDemoUpload = async () => {
    setError('')
    setUploading(true)
    // Simulate upload detection
    await new Promise(r => setTimeout(r, 1200))
    const mockData = {
      session_id: 'demo-' + Date.now(),
      files: files.map((f, i) => ({
        filename:        f.name,
        detected_source: i === 0 ? 'swiggy' : i === 1 ? 'zomato' : 'generic',
        confidence:      i === 0 ? 0.92 : i === 1 ? 0.78 : 0.45,
        needs_confirm:   i !== 0,
      }))
    }
    setSessionData(mockData)
    setUploading(false)
    setStep(2)
  }

  return (
    <div className="p-6 md:p-8 max-w-[760px] mx-auto">

      {/* Header */}
      <div className="mb-8 animate-fade-in">
        <h1 className="text-2xl font-display font-bold text-[var(--text-primary)]">
          Upload Data
        </h1>
        <p className="text-sm text-[var(--text-secondary)] font-body mt-0.5">
          Upload exports from Swiggy, Zomato, Tally, or Petpooja
        </p>
      </div>

      {/* Step indicator */}
      <div className="mb-8 animate-fade-in">
        <StepIndicator step={step} />
      </div>

      {/* ── Step 1: Drop zone ──────────────────────────────────── */}
      {step === 1 && (
        <div className="space-y-5 animate-slide-up">
          <DropZone onFiles={addFiles} disabled={uploading} />

          {files.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold text-[var(--text-muted)] font-body uppercase tracking-wider">
                {files.length} file{files.length !== 1 ? 's' : ''} selected
              </p>
              {files.map(f => (
                <div key={f.name} className="card p-4 flex items-center gap-3 animate-slide-up">
                  <FileText size={16} className="text-saffron-400 flex-shrink-0" />
                  <span className="flex-1 text-sm font-body text-[var(--text-primary)] truncate">{f.name}</span>
                  <span className="text-xs text-[var(--text-muted)] font-body">{(f.size / 1024).toFixed(0)} KB</span>
                  <button onClick={() => removeFile(f.name)}
                    className="p-1 rounded-md text-[var(--text-muted)] hover:text-red-400 transition-colors">
                    <X size={13} />
                  </button>
                </div>
              ))}

              {error && (
                <div className="text-sm text-red-400 font-body bg-red-500/8 border border-red-500/15 rounded-xl px-4 py-3 flex items-center gap-2">
                  <AlertTriangle size={14} className="flex-shrink-0" />
                  {error}
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                <Button
                  loading={uploading}
                  icon={uploading ? null : <ChevronRight size={16} />}
                  onClick={handleUpload}
                  size="lg"
                >
                  {uploading ? 'Uploading…' : 'Upload and detect'}
                </Button>
                <Button variant="ghost" onClick={() => setFiles([])}>
                  Clear all
                </Button>
              </div>
            </div>
          )}

          {/* Guide */}
          <div className="card p-4 mt-2">
            <p className="text-xs font-semibold text-[var(--text-muted)] font-body uppercase tracking-wider mb-3">
              Supported formats
            </p>
            <div className="grid grid-cols-2 gap-2">
              {[
                { src: 'Swiggy', fmt: 'CSV export from Swiggy Partner Portal' },
                { src: 'Zomato', fmt: 'CSV/XLSX from Restaurant Partner dashboard' },
                { src: 'Tally', fmt: 'Daybook or ledger export (.xls)' },
                { src: 'Petpooja', fmt: 'Sales register CSV from POS' },
              ].map(({ src, fmt }) => (
                <div key={src} className="flex gap-2 p-2.5 rounded-lg bg-[var(--bg-subtle)]">
                  <div className="w-5 h-5 rounded bg-saffron-500/15 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Zap size={10} className="text-saffron-400" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-[var(--text-primary)] font-body">{src}</p>
                    <p className="text-[11px] text-[var(--text-muted)] font-body">{fmt}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Step 2: Confirm sources ────────────────────────────── */}
      {step === 2 && sessionData && (
        <div className="space-y-5 animate-slide-up">
          <p className="text-sm text-[var(--text-secondary)] font-body">
            We've analysed your files. Review the detected source types below and correct any misidentifications.
          </p>

          <div className="space-y-3">
            {(sessionData.files || []).map(f => (
              <FileRow
                key={f.filename}
                file={files.find(ff => ff.name === f.filename) || { name: f.filename, size: 0 }}
                detection={f}
                confirmedSource={confirmations[f.filename]}
                onSourceChange={src => setConfirmations(prev => ({ ...prev, [f.filename]: src }))}
                onRemove={() => {}}
              />
            ))}
          </div>

          {error && (
            <div className="text-sm text-red-400 font-body bg-red-500/8 border border-red-500/15 rounded-xl px-4 py-3 flex items-center gap-2">
              <AlertTriangle size={14} className="flex-shrink-0" />
              {error}
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <Button loading={uploading} icon={<Zap size={16} />} onClick={handleConfirm} size="lg">
              {ingestPolling ? 'Processing files…' : uploading ? 'Starting compute…' : 'Confirm & compute metrics'}
            </Button>
            <Button variant="ghost" onClick={() => setStep(1)}>
              Back
            </Button>
          </div>
        </div>
      )}

      {/* ── Step 3: Processing ─────────────────────────────────── */}
      {step === 3 && (
        <div className="flex flex-col items-center text-center py-16 gap-5 animate-fade-in">
          <div className="w-16 h-16 rounded-2xl bg-saffron-500/10 border border-saffron-500/20 flex items-center justify-center animate-glow-pulse">
            <Loader2 size={28} className="text-saffron-500 animate-spin" />
          </div>
          <div>
            <h3 className="text-lg font-display font-semibold text-[var(--text-primary)]">
              Computing your metrics
            </h3>
            <p className="text-sm text-[var(--text-secondary)] font-body mt-1 max-w-xs">
              Redirecting to your analytics report…
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
