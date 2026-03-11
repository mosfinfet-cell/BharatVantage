// lib/api.js — All HTTP calls to BharatVantage backend.
//
// Auth pattern (matches backend exactly):
//   - Authorization: Bearer <access_token>   ← from JWT
//   - X-Outlet-ID: <outlet_uuid>             ← per-request outlet scope
//
// Base URL points to Railway deployment.
// In dev, Vite proxies /api → Railway so CORS is not an issue.

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

// ── Token storage (in-memory + sessionStorage for reload) ────────
// We deliberately avoid localStorage to follow the secure token
// storage pattern. Access token lives in memory; refresh token
// is stored as httpOnly cookie by the backend.
let _accessToken = sessionStorage.getItem('bv_access_token') || null
let _outletId    = sessionStorage.getItem('bv_outlet_id')    || null

export const tokenStore = {
  setToken:    (t) => { _accessToken = t; sessionStorage.setItem('bv_access_token', t) },
  getToken:    ()  => _accessToken,
  clearToken:  ()  => { _accessToken = null; sessionStorage.removeItem('bv_access_token') },

  setOutlet:   (id) => { _outletId = id; sessionStorage.setItem('bv_outlet_id', id) },
  getOutlet:   ()   => _outletId,
  clearOutlet: ()   => { _outletId = null; sessionStorage.removeItem('bv_outlet_id') },

  clear: () => {
    tokenStore.clearToken()
    tokenStore.clearOutlet()
  }
}

// ── Core fetch wrapper ───────────────────────────────────────────
async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  // Attach Bearer token if available
  const token = tokenStore.getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  // Attach outlet context if available
  const outletId = tokenStore.getOutlet()
  if (outletId) headers['X-Outlet-ID'] = outletId

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: 'include', // needed for refresh token cookie
  })

  // 401 → clear session and redirect to login
  if (res.status === 401) {
    tokenStore.clear()
    window.location.href = '/login'
    return
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(
      typeof err.detail === 'string'
        ? err.detail
        : JSON.stringify(err.detail)
    )
  }

  // 204 No Content
  if (res.status === 204) return null
  return res.json()
}

// ── Auth ─────────────────────────────────────────────────────────
export const auth = {
  login: (email, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  register: (email, password, fullName) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName }),
    }),

  refresh: () =>
    request('/auth/refresh', { method: 'POST' }),

  logout: () =>
    request('/auth/logout', { method: 'POST' }),
}

// ── Upload ───────────────────────────────────────────────────────
export const upload = {
  // multipart/form-data — do NOT set Content-Type, browser sets boundary
  uploadFiles: (files) => {
    const formData = new FormData()
    files.forEach(f => formData.append('files', f))

    const token   = tokenStore.getToken()
    const outletId = tokenStore.getOutlet()
    const headers = {}
    if (token)    headers['Authorization'] = `Bearer ${token}`
    if (outletId) headers['X-Outlet-ID']   = outletId

    return fetch(`${BASE_URL}/upload`, {
      method: 'POST',
      headers,
      body: formData,
      credentials: 'include',
    }).then(async res => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(err.detail || 'Upload failed')
      }
      return res.json()
    })
  },

  confirmSession: (sessionId, confirmations) =>
    request(`/upload/${sessionId}/confirm`, {
      method: 'PATCH',
      body: JSON.stringify({ confirmations }),
    }),
}

// ── Compute ──────────────────────────────────────────────────────
export const compute = {
  triggerCompute: (sessionId) =>
    request(`/compute/${sessionId}`, { method: 'POST' }),

  getStatus: (sessionId) =>
    request(`/status/${sessionId}`),

  getMetrics: (sessionId) =>
    request(`/metrics/${sessionId}`),
}

// ── Config ───────────────────────────────────────────────────────
export const config = {
  getConfig: () =>
    request('/config'),

  updateConfig: (data) =>
    request('/config', { method: 'PUT', body: JSON.stringify(data) }),
}

// ── Health ───────────────────────────────────────────────────────
export const health = {
  check: () => fetch('/api/v1/health/ready').then(r => r.json()),
}
