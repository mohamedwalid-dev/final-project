// ─── utils/smartHRService.js ──────────────────────────────────────────────────
// Connects to FastAPI backend at localhost:9000
// Each method returns { data, error } — same pattern as hrService.js

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

const smartHRService = {
  // ── Leave Submission ─────────────────────────────────────────────────────
  // POST /leaves/submit — returns AI decision immediately
  submitLeave: (payload) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/leaves/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json();
    }),

  // ── Salary Review Submission ──────────────────────────────────────────────
  // POST /salary-reviews/submit — returns AI decision immediately
  submitSalaryReview: (payload) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/salary-reviews/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json();
    }),

  // ── Incentive Request Submission ──────────────────────────────────────────
  // POST /incentives/submit — returns AI decision immediately
  submitIncentive: (payload) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/incentives/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json();
    }),

  // ── Absence Event Submission ──────────────────────────────────────────────
  // POST /absences/submit — returns AI decision immediately
  submitAbsence: (payload) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/absences/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json();
    }),

  // ── Fetch Employees (for selectors in modals) ─────────────────────────────
  // GET /employees
  fetchEmployees: () =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees?active_only=true`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      return json.employees || [];
    }),

  // ── Absence Analytics for an employee ────────────────────────────────────
  // GET /employees/{id}/absences
  fetchEmployeeAbsences: (employeeId) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees/${employeeId}/absences`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    }),

  // ── Salary history for an employee ───────────────────────────────────────
  fetchEmployeeSalaryHistory: (employeeId) =>
    fetchSafe(async () => {
      const res = await fetch(`${BASE_URL}/employees/${employeeId}/salary-reviews`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    }),
};

export default smartHRService;