/**
 * services/aiService.js — AI Agent Proxy Layer
 * =============================================
 * Single source of truth for all HTTP calls to the Python FastAPI AI Agent.
 * Node.js routes never talk to Python directly — everything goes through here.
 *
 * Python server: http://localhost:9000  (AI_AGENT_BASE_URL in .env)
 */

import axios from "axios";

// ── Axios instance ─────────────────────────────────────────────────────────

const ai = axios.create({
  baseURL: process.env.AI_AGENT_BASE_URL || "http://localhost:9000",
  timeout: parseInt(process.env.AI_AGENT_TIMEOUT || "35000"),
  headers: { "Content-Type": "application/json" },
});

// ── Error interceptor ──────────────────────────────────────────────────────

ai.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.code === "ECONNREFUSED" || err.code === "ENOTFOUND") {
      const e = new Error(
        "AI Agent unavailable — make sure Python server is running on port 9000"
      );
      e.status = 503;
      e.code   = "AI_AGENT_DOWN";
      return Promise.reject(e);
    }

    if (err.response?.status === 503) {
      const e = new Error(
        "AI model not loaded — run: python training/hr_train.py"
      );
      e.status = 503;
      e.code   = "AI_MODEL_NOT_LOADED";
      return Promise.reject(e);
    }

    if (err.code === "ECONNABORTED") {
      const e = new Error("AI Agent request timed out — try again or poll the decision URL");
      e.status = 504;
      e.code   = "AI_TIMEOUT";
      return Promise.reject(e);
    }

    return Promise.reject(err);
  }
);


// ══════════════════════════════════════════════════════════════════════════════
//  SYSTEM
// ══════════════════════════════════════════════════════════════════════════════

/** GET /health — lightweight cached health check (< 10ms on Python side) */
export const getAgentHealth = () =>
  ai.get("/health").then((r) => r.data);

/** GET /health/detailed — full live health check with DB ping */
export const getAgentHealthDetailed = () =>
  ai.get("/health/detailed").then((r) => r.data);


// ══════════════════════════════════════════════════════════════════════════════
//  HR — LEAVES
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /leaves/submit
 * Returns 202 immediately — AI processes in background.
 * Response: { leave_id, decision_url, db_status: "pending" }
 */
export const submitLeaveToAgent = (leaveData) =>
  ai.post("/leaves/submit", leaveData).then((r) => r.data);

/**
 * GET /leaves/:leaveId/decision
 * Poll until status is approved | rejected | escalated.
 */
export const getLeaveDecision = (leaveId) =>
  ai.get(`/leaves/${leaveId}/decision`).then((r) => r.data);

/**
 * GET /leaves/:leaveId/audit
 * Full decision audit trail for a leave request.
 */
export const getLeaveAudit = (leaveId) =>
  ai.get(`/leaves/${leaveId}/audit`).then((r) => r.data);


// ══════════════════════════════════════════════════════════════════════════════
//  HR — SALARY REVIEWS
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /salary-reviews/submit
 * Returns 202 immediately.
 * Response: { review_id, decision_url, explain_url }
 */
export const submitSalaryReviewToAgent = (reviewData) =>
  ai.post("/salary-reviews/submit", reviewData).then((r) => r.data);

/**
 * GET /salary-reviews/:reviewId/decision
 * Polls up to 45s on Python side before returning.
 */
export const getSalaryReviewDecision = (reviewId) =>
  ai.get(`/salary-reviews/${reviewId}/decision`).then((r) => r.data);

/**
 * GET /salary-reviews/:reviewId/explain
 * Full explainability breakdown (score, weights, decision factors).
 */
export const getSalaryReviewExplanation = (reviewId) =>
  ai.get(`/salary-reviews/${reviewId}/explain`).then((r) => r.data);


// ══════════════════════════════════════════════════════════════════════════════
//  HR — ABSENCE EVENTS
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /absences/submit
 * Returns 202 immediately.
 * Response: { absence_id, decision_url }
 */
export const submitAbsenceToAgent = (absenceData) =>
  ai.post("/absences/submit", absenceData).then((r) => r.data);

/**
 * GET /absences/:absenceId/decision
 */
export const getAbsenceDecision = (absenceId) =>
  ai.get(`/absences/${absenceId}/decision`).then((r) => r.data);


// ══════════════════════════════════════════════════════════════════════════════
//  HR — INCENTIVE REQUESTS
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /incentives/submit
 * Returns 202 immediately.
 * Response: { incentive_id, decision_url }
 */
export const submitIncentiveToAgent = (incentiveData) =>
  ai.post("/incentives/submit", incentiveData).then((r) => r.data);

/**
 * GET /incentives/:incentiveId/decision
 */
export const getIncentiveDecision = (incentiveId) =>
  ai.get(`/incentives/${incentiveId}/decision`).then((r) => r.data);


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /finance/predict-risk
 * Synchronous ML prediction — returns decision, risk_score, reasons.
 */
export const predictInvoiceRisk = (riskInput) =>
  ai.post("/finance/predict-risk", riskInput).then((r) => r.data);

/**
 * GET /finance/actions/dashboard-data?days=7
 * Layered cache (memory → Redis → MongoDB) on Python side.
 */
export const getAIFinanceDashboard = (days = 7) =>
  ai.get(`/finance/actions/dashboard-data?days=${days}`).then((r) => r.data);

/**
 * GET /finance/model/info
 * Finance ML model metadata (version, accuracy, thresholds).
 */
export const getFinanceModelInfo = () =>
  ai.get("/finance/model/info").then((r) => r.data);