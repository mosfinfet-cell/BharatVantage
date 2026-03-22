/**
 * api.js — BharatVantage v1.1 HTTP client.
 *
 * All calls include:
 *   Authorization: Bearer <access_token>  (from AuthContext)
 *   X-Outlet-ID: <outlet_uuid>            (from AuthContext)
 *
 * New in v1.1:
 *   - manual entries (cash drawer + platform rating)
 *   - CA export endpoint
 *   - updated metrics response shape
 */

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// ── Token store (sessionStorage) ──────────────────────────────────────────
// Used by AuthContext to persist token and outletId across page refreshes.
export const tokenStore = {
  getToken:     ()  => { const v = sessionStorage.getItem('bv_token');     return (v && v !== 'null') ? v : null; },
  setToken:     (t) => sessionStorage.setItem('bv_token', t),
  clearToken:   ()  => sessionStorage.removeItem('bv_token'),
  getOutlet:    ()  => { const v = sessionStorage.getItem('bv_outlet_id'); return (v && v !== 'null') ? v : null; },
  setOutlet:    (id)=> sessionStorage.setItem('bv_outlet_id', id),
  clearOutlet:  ()  => sessionStorage.removeItem('bv_outlet_id'),
  clear:        ()  => { sessionStorage.removeItem('bv_token'); sessionStorage.removeItem('bv_outlet_id'); },
};



// ── Core request helper ────────────────────────────────────────────────────
async function request(method, path, body = null, token = null, outletId = null) {
  const headers = { "Content-Type": "application/json" };
  // Guard: tokenStore returns null as the string "null" if key was never set.
  // Never send "null" as a header value — it reaches the backend as a literal string.
  if (token && token !== 'null')       headers["Authorization"] = `Bearer ${token}`;
  if (outletId && outletId !== 'null') headers["X-Outlet-ID"]   = outletId;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${BASE}${path}`, opts);

  // 202 Accepted = not ready yet (not an error)
  if (res.status === 202) {
    const data = await res.json().catch(() => ({}));
    return { __status: 202, ...data };
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────
export const auth = {
  register: (body) =>
    request("POST", "/auth/register", body),

  login: (email, password) =>
    request("POST", "/auth/login", { email, password }),

  refresh: () =>
    request("POST", "/auth/refresh"),

  logout: (token) =>
    request("POST", "/auth/logout", null, token),
};

// ── Config (outlets) ──────────────────────────────────────────────────────
export const config = {
  listOutlets: (token) =>
    request("GET", "/config/outlets", null, token),

  createOutlet: (token, body) =>
    request("POST", "/config/outlets", body, token),

  /**
   * Update outlet config — packaging tiers, outlet_type, etc.
   * body: { outlet_type?, packaging_cost_tier1?, packaging_cost_tier2?,
   *         packaging_cost_tier3?, packaging_configured?, gst_rate_pct?,
   *         monthly_rent?, monthly_utilities?, seat_count? }
   */
  updateOutlet: (token, outletId, body) =>
    request("PATCH", `/config/outlets/${outletId}`, body, token),
};

// ── Upload ────────────────────────────────────────────────────────────────
export const upload = {
  /**
   * Upload one or more files. Returns { session_id, files, needs_confirm }.
   * Uses FormData — does NOT use the JSON request helper.
   * Backend expects field name "files" (plural) — do not change.
   */
  uploadFile: async (token, outletId, files) => {
    const form = new FormData();
    // Accept single File or array of Files
    const fileList = Array.isArray(files) ? files : [files];
    fileList.forEach(f => form.append("files", f));

    const res = await fetch(`${BASE}/upload`, {
      method:  "POST",
      headers: {
        Authorization:  `Bearer ${token}`,
        "X-Outlet-ID":  outletId,
      },
      body: form,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  /**
   * Confirm source types for files in a session.
   * confirmations: [{ file_id, confirmed_source }]
   * Called by UploadPage as uploadApi.confirmSession(sessionId, confirmations)
   */
  confirmSession: (sessionId, confirmations) => {
    const token    = tokenStore.getToken();
    const outletId = tokenStore.getOutlet();
    return request(
      "PATCH",
      `/upload/${sessionId}/confirm`,
      { confirmations },
      token,
      outletId,
    );
  },

  // Legacy alias — kept for backward compatibility
  confirm: (token, outletId, sessionId) =>
    request("PATCH", `/upload/${sessionId}/confirm`, null, token, outletId),
};

// ── Compute & Metrics ─────────────────────────────────────────────────────
export const compute = {
  /** Enqueue compute job. Returns { session_id, job_id, status }. */
  enqueue: (token, outletId, sessionId) =>
    request("POST", `/compute/${sessionId}`, null, token, outletId),

  /** Poll session status. Returns { ready, compute_status, ingest_status, ... }. */
  getStatus: (token, outletId, sessionId) =>
    request("GET", `/status/${sessionId}`, null, token, outletId),

  /**
   * Fetch computed metrics for a session.
   *
   * Returns v1.1 shape:
   * {
   *   session_id, computed_at, schema_version, is_stale,
   *   outlet_type,  // 'dine_in' | 'hybrid' | 'cloud_kitchen'
   *   period_start, period_end,
   *   sufficiency:  { metric_key: 'complete'|'estimated'|'locked'|'partial' },
   *   alerts:       [ { priority, metric, message, color } ],
   *   metrics: {
   *     // Layer 1 (hybrid/shared)
   *     total_earnings, staff_cost_pct, prime_cost_pct, kitchen_conflict_days,
   *     channel_comparison,
   *     // Dine-in tab
   *     dine_in: { today_earnings, cash_reconciliation, avg_bill_per_table, ... },
   *     // Online tab
   *     online: { pending_settlements, payout_bridge, platform_earnings,
   *               true_order_margin, penalties, ad_spend_efficiency,
   *               item_channel_margin, packaging_cost_config },
   *     // CA Export
   *     ca_export: { completeness, gst_on_sales, ... }
   *   }
   * }
   */
  getMetrics: (token, outletId, sessionId) =>
    request("GET", `/metrics/${sessionId}`, null, token, outletId),
};

// ── Manual Entries ────────────────────────────────────────────────────────
export const manualEntry = {
  /**
   * Create a manual entry.
   * @param {string} entryType  'cash_drawer' | 'platform_rating'
   * @param {string} entryDate  'YYYY-MM-DD'
   * @param {number} value      ₹ amount (cash) OR rating float 1.0–5.0
   * @param {string} platform   'swiggy' | 'zomato' — required for ratings
   */
  create: (token, outletId, { entryType, entryDate, value, platform = null }) =>
    request("POST", "/manual-entry", {
      entry_type: entryType,
      entry_date: entryDate,
      value,
      platform,
    }, token, outletId),

  /**
   * List manual entries. Optional filter by entryType.
   * Returns last 90 entries ordered by entry_date desc.
   */
  list: (token, outletId, entryType = null) => {
    const qs = entryType ? `?entry_type=${entryType}` : "";
    return request("GET", `/manual-entries${qs}`, null, token, outletId);
  },
};

// ── Actions ───────────────────────────────────────────────────────────────
export const actions = {
  /**
   * Raise a dispute for recoverable penalties.
   * Generates a structured dispute list matching platform portal format.
   * @param {Array} orders  Array of { id, date, platform, amount, reason }
   */
  raiseDispute: (token, outletId, { sessionId, orders }) =>
    request("POST", "/actions/dispute", {
      session_id: sessionId,
      orders,
    }, token, outletId),

  /**
   * Export CA GST Reconciliation Report.
   * @param {string} format  'pdf' | 'csv'
   */
  exportCA: (token, outletId, { sessionId, format = "pdf" }) =>
    request("POST", "/actions/export", {
      export_type: "gst_reconciliation",
      session_id:  sessionId,
      format,
    }, token, outletId),

  /** Check export status / get download URL. */
  getExport: (token, outletId, exportId) =>
    request("GET", `/actions/export/${exportId}`, null, token, outletId),

  /** Flag a shift for manager review. */
  flagShift: (token, outletId, { sessionId, shiftLabel, reason }) =>
    request("POST", "/actions/flag-shift", {
      session_id:  sessionId,
      shift_label: shiftLabel,
      reason,
    }, token, outletId),
};

// ── Health ────────────────────────────────────────────────────────────────
export const health = {
  check: () => fetch(`${BASE.replace("/api/v1", "")}/health`).then(r => r.json()),
};
