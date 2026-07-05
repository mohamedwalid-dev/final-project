// ─── utils/smartHRService.js ──────────────────────────────────────────────────
// Connects to FastAPI backend at localhost:9000 (v6.5 — Node.js API Edition)
// Each method returns { data, error } — same pattern as hrService.js
//
// IMPORTANT: the /submit endpoints are ASYNC. The AI decision (ML + LLM) takes
// 5–15s, so the backend answers with 202 Accepted and a body like
//   { message, leave_id, db_status: "pending", decision_url, ... }
// The final decision is then read from  GET /{entity}/{id}/decision.
// So after every submit we poll that endpoint until a terminal decision arrives
// (or we hit the timeout), and return the final decision merged with the
// original submit response.
//
// ── v6.5 backend changes reflected here ─────────────────────────────────────
// 1. Submit responses use "db_status": "pending" (not "status": "processing").
//    isPending() now checks db_status too.
// 2. Decision endpoints return the terminal state as "status" (e.g. "approved",
//    "rejected", "escalated", "recorded", "deducted", ...) — there usually is
//    NO separate top-level "decision" field for leaves any more (leaves nest
//    the full record under "leave"; salary/incentive/absence keep "decision"
//    at top level too, so we check both to stay compatible).
// 3. GET /employees and GET /employees/{id} now ALWAYS return 503 — there is
//    no /hr/employees route in the Node.js API yet. fetchEmployees() and
//    searchEmployees() now surface that as a clear, explicit error instead of
//    silently returning an empty list.
// 4. /employees/{id}/absences and /employees/{id}/salary-reviews still work,
//    but response shape is now { employee_id, count, absences|reviews, ... }.

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:9000";

const normalizeError = (err) => {
  if (err?.name === "AbortError") return null;
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "An unexpected error occurred";
};

async function fetchSafe(fn) {
  try {
    const data = await fn();
    return { data, error: null };
  } catch (err) {
    const error = normalizeError(err);
    if (!error) return { data: null, error: null };
    return { data: null, error };
  }
}

// Extracts a readable message out of a FastAPI error body.
// v6.5 error shapes:
//   - HTTPException(detail=...)              -> { detail: "..." }
//   - NodeAPIError handler                    -> { status:"error", detail:"...", type:"NodeAPIError", node_endpoint, path, timestamp }
//   - generic Exception handler                -> { status:"error", detail:"Internal server error: ...", type, path, timestamp }
const extractErrorDetail = (body, fallback) => {
  if (!body) return fallback;
  if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  if (typeof body.message === "string" && body.message.trim()) return body.message;
  return fallback;
};

// ── Async-decision helpers ───────────────────────────────────────────────────

// A response is "pending" when there is no terminal AI decision yet.
// v6.5 submit responses carry db_status:"pending" (not status:"processing").
// v6.5 decision responses carry the terminal state directly in "status"
// (e.g. "approved" / "rejected" / "escalated" / "recorded" / "deducted" / ...),
// so anything that ISN'T one of the known terminal states counts as pending.
const TERMINAL_STATUSES = new Set([
  // leaves
  "approved", "rejected", "escalated",
  // salary reviews
  "deferred",
  // incentives
  "partial", "escalated_ceo",
  // absences
  "recorded", "warned_written", "warned_formal",
  "deducted", "deducted_double",
  "suspension_review", "termination_review",
]);

const isPending = (d) => {
  if (!d) return true;
  if (d.db_status === "pending") return true;
  if (d.status === "processing" || d.status === "pending") return true;
  if (d.decision === "processing" || d.decision === "pending") return true;
  const state = d.status ?? d.decision;
  if (state == null) return true;
  return !TERMINAL_STATUSES.has(state);
};

// Pull the entity id out of a submit response (field name varies per entity).
const extractId = (d, ...keys) => {
  for (const k of [...keys, "id"]) {
    if (d?.[k] != null) return d[k];
  }
  return null;
};

const sleep = (ms, signal) =>
  new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    if (signal) {
      signal.addEventListener(
        "abort",
        () => {
          clearTimeout(t);
          reject(new DOMException("Aborted", "AbortError"));
        },
        { once: true }
      );
    }
  });

// Poll GET /{path}/{id}/decision until the decision is terminal or we time out.
// `seed` is the original submit response — returned (unchanged) if we time out,
// so the UI can still show a "processing" state instead of freezing silently.
async function pollDecision(path, id, seed, { intervalMs = 1500, maxMs = 30000, signal } = {}) {
  const deadline = Date.now() + maxMs;
  let last = seed;

  while (Date.now() < deadline) {
    await sleep(intervalMs, signal);
    try {
      const res = await fetch(`${BASE_URL}/${path}/${id}/decision`, { signal });
      if (!res.ok) continue; // transient (e.g. not-ready yet) — keep polling
      const data = await res.json();
      last = { ...seed, ...data }; // merge so submit-only fields (ids) survive
      if (!isPending(data)) return last; // terminal decision reached
    } catch (err) {
      if (err?.name === "AbortError") throw err;
      // network blip — keep polling until the deadline
    }
  }
  return last; // timed out: return the latest known state (still "pending")
}

// Shared submit runner: POST -> (maybe 202 pending) -> poll decision.
async function submitAndPoll({ endpoint, payload, signal, idKeys, decisionPath }) {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(extractErrorDetail(err, `HTTP ${res.status}`));
  }
  const data = await res.json();
  if (!isPending(data)) return data;
  const id = extractId(data, ...idKeys);
  if (id == null) return data;
  return pollDecision(decisionPath, id, data, { signal });
}

const smartHRService = {
  // ── Leave Submission ─────────────────────────────────────────────────────
  // POST /leaves/submit  → 202 { message, leave_id, db_status:"pending", decision_url }
  // poll  GET /leaves/{id}/decision → { leave_id, status, leave }
  submitLeave: (payload, signal) =>
    fetchSafe(() =>
      submitAndPoll({
        endpoint: "/leaves/submit",
        payload,
        signal,
        idKeys: ["leave_id"],
        decisionPath: "leaves",
      })
    ),

  // ── Salary Review Submission ──────────────────────────────────────────────
  // POST /salary-reviews/submit  → 202 { message, review_id, db_status:"pending", decision_url, explain_url }
  // poll  GET /salary-reviews/{id}/decision → { review_id, decision, status, review }
  submitSalaryReview: (payload, signal) =>
    fetchSafe(() =>
      submitAndPoll({
        endpoint: "/salary-reviews/submit",
        payload,
        signal,
        idKeys: ["review_id"],
        decisionPath: "salary-reviews",
      })
    ),

  // ── Incentive Request Submission ──────────────────────────────────────────
  // POST /incentives/submit  → 202 { message, incentive_id, incentive_type, db_status:"pending", decision_url }
  // poll  GET /incentives/{id}/decision → { incentive_id, decision, status, approved_amount, incentive }
  submitIncentive: (payload, signal) =>
    fetchSafe(() =>
      submitAndPoll({
        endpoint: "/incentives/submit",
        payload,
        signal,
        idKeys: ["incentive_id"],
        decisionPath: "incentives",
      })
    ),

  // ── Absence Event Submission ──────────────────────────────────────────────
  // POST /absences/submit  → 202 { message, absence_id, absence_date, absence_type, db_status:"pending", decision_url }
  // poll  GET /absences/{id}/decision → { absence_id, decision, classification, status, payroll_deduction_days, escalation_required, absence }
  submitAbsence: (payload, signal) =>
    fetchSafe(() =>
      submitAndPoll({
        endpoint: "/absences/submit",
        payload,
        signal,
        idKeys: ["absence_id", "event_id"],
        decisionPath: "absences",
      })
    ),

  // ── Fetch Employees (for selectors in modals) ─────────────────────────────
  // ⚠️ v6.5: GET /employees is DISABLED (503) — there is no /hr/employees
  // route in the Node.js API yet. We surface this as a clear error instead
  // of silently returning an empty list, so the UI can show a real message
  // ("Employee directory isn't available yet") instead of looking broken.
  fetchEmployees: () =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees?active_only=true`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = extractErrorDetail(
          err,
          res.status === 503
            ? "Employee directory isn't available yet (no /hr/employees route in the Node.js API)."
            : `HTTP ${res.status}`
        );
        throw new Error(detail);
      }
      const json = await res.json();
      return json.employees || [];
    }),

  // ── Search Employees (by name or id) ──────────────────────────────────────
  // ⚠️ v6.5: same 503 caveat as fetchEmployees — there's no dedicated search
  // endpoint and the underlying /employees list is currently disabled.
  searchEmployees: (query) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees?active_only=true`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = extractErrorDetail(
          err,
          res.status === 503
            ? "Employee search isn't available yet (no /hr/employees route in the Node.js API)."
            : `HTTP ${res.status}`
        );
        throw new Error(detail);
      }
      const json = await res.json();
      const list = json.employees || [];
      const q = String(query || "").trim().toLowerCase();
      if (!q) return list;
      return list.filter(
        (e) =>
          String(e.name || "").toLowerCase().includes(q) ||
          String(e.id || "").toLowerCase().includes(q)
      );
    }),

  // ── Absence Analytics for an employee ────────────────────────────────────
  // GET /employees/{id}/absences → { employee_id, count, unexcused_total, absences }
  fetchEmployeeAbsences: (employeeId) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees/${employeeId}/absences`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(extractErrorDetail(err, `HTTP ${res.status}`));
      }
      return res.json();
    }),

  // ── Salary history for an employee ───────────────────────────────────────
  // GET /employees/{id}/salary-reviews → { employee_id, count, reviews }
  fetchEmployeeSalaryHistory: (employeeId) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees/${employeeId}/salary-reviews`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(extractErrorDetail(err, `HTTP ${res.status}`));
      }
      return res.json();
    }),

  // ── Incentive history for an employee ────────────────────────────────────
  // NEW in v6.5 client: GET /employees/{id}/incentives → { employee_id, count, total_approved_egp, incentives }
  // (endpoint already existed server-side; wasn't wired into the old service)
  fetchEmployeeIncentives: (employeeId) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees/${employeeId}/incentives`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(extractErrorDetail(err, `HTTP ${res.status}`));
      }
      return res.json();
    }),

  // ── Leave history for an employee ────────────────────────────────────────
  // NEW in v6.5 client: GET /employees/{id}/leaves → { employee_id, count, leaves }
  fetchEmployeeLeaves: (employeeId) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees/${employeeId}/leaves`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(extractErrorDetail(err, `HTTP ${res.status}`));
      }
      return res.json();
    }),
};

export default smartHRService;