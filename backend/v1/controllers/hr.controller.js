/**
 * controllers/hr.controller.js — HR Domain Controllers
 * =======================================================
 * Covers: Leave / SalaryReview / AbsenceEvent / IncentiveRequest
 *         + HRDomainAudit + BalanceAuditLog + Dashboard
 *
 * ✅ AI Integration (added):
 *   - createLeave          → submits to Python AI Agent, saves agent_ref_id
 *   - createSalaryReview   → submits to Python AI Agent, saves agent_ref_id
 *   - createAbsenceEvent   → submits to Python AI Agent, saves agent_ref_id
 *   - createIncentiveRequest → submits to Python AI Agent, saves agent_ref_id
 *   - getLeaveDecisionById         → polls Python for AI result
 *   - getSalaryReviewDecisionById  → polls Python for AI result
 *   - getAbsenceDecisionById       → polls Python for AI result
 *   - getIncentiveDecisionById     → polls Python for AI result
 */

import mongoose from "mongoose";
import {
  Leave,
  SalaryReview,
  AbsenceEvent,
  IncentiveRequest,
  HRDomainAudit,
  BalanceAuditLog,
} from "../models/hr.model.js";

import { sendSuccess, sendFailed as sendError } from "../utils/response.js";

import {
  getLeaveDecision,
  getSalaryReviewDecision,
  getAbsenceDecision,
  getIncentiveDecision,
} from "../services/aiService.js";

// ── Helpers ────────────────────────────────────────────────────────────────

const toOid = (id) => {
  try {
    return new mongoose.Types.ObjectId(String(id));
  } catch {
    return null;
  }
};

const resolveOid = (res, id) => {
  const oid = toOid(id);
  if (!oid) {
    sendError(res, `Invalid id: ${id}`, 400);
    return null;
  }
  return oid;
};

/**
 * Safely sync an AI decision back into the local MongoDB document.
 * Called after polling Python — updates status + ai fields in one shot.
 */
const syncLeaveDecision = async (localId, agentResult) => {
  const { status, leave } = agentResult;
  if (!status || status === "pending" || status === "processing") return;

  await Leave.findByIdAndUpdate(localId, {
    $set: {
      agent_status:     status,
      ai_decision:      (leave?.ai_decision     || "").substring(0, 100),
      confidence_score: leave?.confidence_score  || 0,
      decision_reason:  (leave?.decision_reason  || "").substring(0, 1000),
      decision_source:  leave?.decision_source   || "ai_agent",
      llm_used:         leave?.llm_used          ?? true,
      request_id:       (leave?.request_id       || "").substring(0, 100),
      resolved_at:      new Date(),
    },
  });
};

const syncSalaryDecision = async (localId, agentResult) => {
  const { status, review } = agentResult;
  if (!status || status === "pending" || status === "processing") return;

  await SalaryReview.findByIdAndUpdate(localId, {
    $set: {
      agent_status:              status,
      ai_decision:               (review?.ai_decision              || "").substring(0, 100),
      confidence_score:          review?.confidence_score           || 0,
      decision_reason:           (review?.decision_reason           || "").substring(0, 1000),
      recommended_increment_pct: review?.recommended_increment_pct ?? null,
      request_id:                (review?.request_id               || "").substring(0, 100),
      resolved_at:               new Date(),
    },
  });
};

const syncAbsenceDecision = async (localId, agentResult) => {
  const { status, absence } = agentResult;
  if (!status || status === "pending" || status === "processing") return;

  await AbsenceEvent.findByIdAndUpdate(localId, {
    $set: {
      agent_status:           status,
      ai_decision:            (absence?.ai_decision        || "").substring(0, 100),
      ai_classification:      (absence?.ai_classification  || "").substring(0, 100),
      confidence_score:       absence?.confidence_score     || 0,
      decision_reason:        (absence?.decision_reason     || "").substring(0, 1000),
      payroll_deduction_days: absence?.payroll_deduction_days || 0,
      escalation_required:    Boolean(absence?.escalation_required),
      request_id:             (absence?.request_id          || "").substring(0, 100),
      resolved_at:            new Date(),
    },
  });
};

const syncIncentiveDecision = async (localId, agentResult) => {
  const { status, incentive } = agentResult;
  if (!status || status === "pending" || status === "processing") return;

  await IncentiveRequest.findByIdAndUpdate(localId, {
    $set: {
      agent_status:       status,
      ai_decision:        (incentive?.ai_decision     || "").substring(0, 100),
      confidence_score:   incentive?.confidence_score  || 0,
      decision_reason:    (incentive?.decision_reason  || "").substring(0, 1000),
      approved_amount_egp:incentive?.approved_amount_egp ?? null,
      request_id:         (incentive?.request_id       || "").substring(0, 100),
      resolved_at:        new Date(),
    },
  });
};


// ══════════════════════════════════════════════════════════════════════════════
//  LEAVE
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /v1/hr/leaves
 * Saves the leave request locally and returns immediately (202).
 *
 * ⚠️ FIX: previously called submitLeaveToAgent() here, which makes an
 * outbound HTTP call to the Python FastAPI service (POST
 * /leaves/submit). That Python endpoint is the one that calls INTO
 * this Node endpoint (via NodeAPIClient -> POST /hr/leaves) as part of
 * hr_db.create_leave_request(). This created a synchronous request
 * loop back to the same FastAPI service that was already waiting on
 * this very request — a deadlock resolved only by a ~10s timeout,
 * which then tripped the Python-side circuit breaker (same root cause
 * documented in createAbsenceEvent() below).
 *
 * Fix: just persist the record and return. The Python trigger engine
 * already polls GET /hr/leaves/pending on its own schedule
 * (job_scan_pending_leaves, see core/trigger.py) and will pick this up
 * and run the AI workflow without a synchronous handshake here.
 */
export const createLeave = async (req, res) => {
  try {
    const leave = await Leave.create({
      ...req.body,
      agent_status: "pending",
      submitted_at: new Date(),
    });

    return sendSuccess(
      res,
      {
        leave_id:     leave._id,
        agent_status: "pending",
        decision_url: `/v1/hr/leaves/${leave._id}/decision`,
        note:         "Saved — background trigger engine will process this automatically",
      },
      "Leave request submitted",
      202
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

/**
 * GET /v1/hr/leaves/:id/decision
 * Polls Python for the AI decision and syncs result back to local MongoDB.
 */
export const getLeaveDecisionById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const leave = await Leave.findById(oid);
    if (!leave) return sendError(res, "Leave not found", 404);

    // Already resolved locally — return immediately
    if (leave.agent_status && !["pending", "processing", "agent_unavailable"].includes(leave.agent_status)) {
      return sendSuccess(res, {
        leave_id:     leave._id,
        agent_ref_id: leave.agent_ref_id,
        status:       leave.agent_status,
        ai_decision:  leave.ai_decision,
        leave,
      }, "Leave decision fetched");
    }

    if (!leave.agent_ref_id) {
      return sendError(res, "No agent_ref_id — this leave was not submitted to the AI agent", 400);
    }

    // Poll Python for decision
    const agentResult = await getLeaveDecision(leave.agent_ref_id);

    // Sync result back to local MongoDB
    await syncLeaveDecision(oid, agentResult);

    const updated = await Leave.findById(oid);
    return sendSuccess(
      res,
      {
        leave_id:     leave._id,
        agent_ref_id: leave.agent_ref_id,
        status:       agentResult.status,
        ai_decision:  agentResult.leave?.ai_decision,
        agent_result: agentResult,
        leave:        updated,
      },
      "Leave decision fetched"
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getAllLeaves = async (req, res) => {
  try {
    const { status, employee_id, leave_type, limit = 50, skip = 0 } = req.query;

    const filter = {};
    if (status)      filter.status      = status;
    if (employee_id) filter.employee_id = employee_id;
    if (leave_type)  filter.leave_type  = leave_type;

    const [leaves, total] = await Promise.all([
      Leave.find(filter).populate("employee_id").sort({ created_at: -1 }).skip(Number(skip)).limit(Number(limit)),
      Leave.countDocuments(filter),
    ]);

    return sendSuccess(res, { leaves, total, skip: Number(skip), limit: Number(limit) }, "Leaves fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getPendingLeaves = async (req, res) => {
  try {
    const leaves = await Leave.find({ status: "pending" }).populate("employee_id").sort({ created_at: 1 });
    return sendSuccess(res, leaves, "Pending leaves fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getLeaveById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const leave = await Leave.findById(oid).populate("employee_id");
    if (!leave) return sendError(res, "Leave not found", 404);

    return sendSuccess(res, leave, "Leave fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getEmployeeLeaves = async (req, res) => {
  try {
    const { employee_id } = req.params;
    const limit = Number(req.query.limit) || 50;

    const leaves = await Leave.find({ employee_id })
      .populate("employee_id")
      .sort({ created_at: -1 })
      .limit(limit);

    return sendSuccess(res, leaves, "Employee leaves fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const updateLeaveStatus = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const {
      status, ai_decision = "", confidence_score = 0,
      decision_reason = "", decision_source = "",
      tier = 2, llm_used = false, request_id = "", notes = "",
    } = req.body;

    const updated = await Leave.findByIdAndUpdate(
      oid,
      {
        $set: {
          status,
          ai_decision:      ai_decision.substring(0, 100),
          confidence_score: Number(confidence_score),
          decision_reason:  decision_reason.substring(0, 1000),
          decision_source,
          tier:             Number(tier),
          llm_used:         Boolean(llm_used),
          request_id:       request_id.substring(0, 100),
          notes:            notes.substring(0, 500),
        },
      },
      { new: true, runValidators: true }
    );

    if (!updated) return sendError(res, "Leave not found", 404);
    return sendSuccess(res, updated, "Leave status updated");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const deleteLeave = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const deleted = await Leave.findByIdAndDelete(oid);
    if (!deleted) return sendError(res, "Leave not found", 404);

    return sendSuccess(res, [], "Leave deleted");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  SALARY REVIEW
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /v1/hr/salary-reviews
 * Saves the salary review locally and returns immediately (202).
 * See createLeave() above for why the old submitSalaryReviewToAgent()
 * loopback call was removed — same deadlock pattern.
 */
export const createSalaryReview = async (req, res) => {
  try {
    const review = await SalaryReview.create({
      ...req.body,
      agent_status: "pending",
      submitted_at: new Date(),
    });

    return sendSuccess(
      res,
      {
        review_id:    review._id,
        agent_status: "pending",
        decision_url: `/v1/hr/salary-reviews/${review._id}/decision`,
        note:         "Saved — background trigger engine will process this automatically",
      },
      "Salary review submitted",
      202
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};
/**
 * GET /v1/hr/salary-reviews/:id/decision
 */
export const getSalaryReviewDecisionById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const review = await SalaryReview.findById(oid);
    if (!review) return sendError(res, "Salary review not found", 404);

    if (review.agent_status && !["pending", "processing", "agent_unavailable"].includes(review.agent_status)) {
      return sendSuccess(res, {
        review_id:    review._id,
        agent_ref_id: review.agent_ref_id,
        status:       review.agent_status,
        ai_decision:  review.ai_decision,
        review,
      }, "Salary review decision fetched");
    }

    if (!review.agent_ref_id) {
      return sendError(res, "No agent_ref_id — this review was not submitted to the AI agent", 400);
    }

    const agentResult = await getSalaryReviewDecision(review.agent_ref_id);
    await syncSalaryDecision(oid, agentResult);

    const updated = await SalaryReview.findById(oid);
    return sendSuccess(
      res,
      {
        review_id:    review._id,
        agent_ref_id: review.agent_ref_id,
        status:       agentResult.status,
        ai_decision:  agentResult.review?.ai_decision,
        agent_result: agentResult,
        review:       updated,
      },
      "Salary review decision fetched"
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getAllSalaryReviews = async (req, res) => {
  try {
    const { status, employee_id, limit = 20, skip = 0 } = req.query;
    const filter = {};
    if (status)      filter.status      = status;
    if (employee_id) filter.employee_id = employee_id;

    const [reviews, total] = await Promise.all([
      SalaryReview.find(filter).populate("employee_id").sort({ created_at: -1 }).skip(Number(skip)).limit(Number(limit)),
      SalaryReview.countDocuments(filter),
    ]);

    return sendSuccess(res, { reviews, total }, "Salary reviews fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getPendingSalaryReviews = async (req, res) => {
  try {
    const reviews = await SalaryReview.find({ status: "pending" }).populate("employee_id").sort({ created_at: 1 });
    return sendSuccess(res, reviews, "Pending salary reviews fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getSalaryReviewById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const review = await SalaryReview.findById(oid).populate("employee_id");
    if (!review) return sendError(res, "Salary review not found", 404);

    return sendSuccess(res, review, "Salary review fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const updateSalaryReviewStatus = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const {
      status, ai_decision = "", confidence_score = 0,
      decision_reason = "", recommended_increment_pct, request_id = "",
    } = req.body;

    const updated = await SalaryReview.findByIdAndUpdate(
      oid,
      {
        $set: {
          status,
          ai_decision:               ai_decision.substring(0, 100),
          confidence_score:          Number(confidence_score),
          decision_reason:           decision_reason.substring(0, 1000),
          recommended_increment_pct: recommended_increment_pct ?? null,
          request_id:                request_id.substring(0, 100),
        },
      },
      { new: true, runValidators: true }
    );

    if (!updated) return sendError(res, "Salary review not found", 404);
    return sendSuccess(res, updated, "Salary review updated");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const deleteSalaryReview = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const deleted = await SalaryReview.findByIdAndDelete(oid);
    if (!deleted) return sendError(res, "Salary review not found", 404);

    return sendSuccess(res, [], "Salary review deleted");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  ABSENCE EVENT
// ══════════════════════════════════════════════════════════════════════════════
/**
 * POST /v1/hr/absence-events
 * Saves the absence event locally and returns immediately (202).
 *
 * ⚠️ v2 FIX: This used to call submitAbsenceToAgent() here, which makes
 * an outbound HTTP call to the Python FastAPI service (POST
 * /absences/submit). But THAT Python endpoint is the one that calls
 * INTO this Node endpoint in the first place (via NodeAPIClient ->
 * POST /hr/absence-events) as part of hr_db.create_absence_event().
 * So the old code created a synchronous request loop back to the same
 * FastAPI service that was already waiting on this very request:
 *
 *   FastAPI  POST /absences/submit
 *     -> Node   POST /hr/absence-events   (this handler)
 *          -> submitAbsenceToAgent()
 *               -> FastAPI  POST /absences/submit  (loopback!)
 *
 * That's a deadlock: the original FastAPI request handler can't finish
 * until this Node call returns, but this Node call was waiting on a
 * NEW request to the same (busy) FastAPI service. It always resolved
 * via httpx.ReadTimeout after ~10s, tripped the Python-side circuit
 * breaker, and surfaced as 502s.
 *
 * Fix: just persist the record and return. The Python trigger engine
 * already polls GET /hr/absence-events/pending on its own schedule
 * (job_scan_pending_absences, see core/trigger.py) and will pick this
 * up and run the AI workflow without needing a synchronous handshake
 * here at all.
 */
export const createAbsenceEvent = async (req, res) => {
  try {
    const event = await AbsenceEvent.create({
      ...req.body,
      agent_status: "pending",
      submitted_at: new Date(),
    });

    return sendSuccess(
      res,
      {
        absence_id:   event._id,
        agent_status: "pending",
        decision_url: `/v1/hr/absence-events/${event._id}/decision`,
        note:         "Saved — background trigger engine will process this automatically",
      },
      "Absence event submitted",
      202
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

/**
 * GET /v1/hr/absence-events/:id/decision
 */
export const getAbsenceDecisionById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const event = await AbsenceEvent.findById(oid);
    if (!event) return sendError(res, "Absence event not found", 404);

    if (event.agent_status && !["pending", "processing", "agent_unavailable"].includes(event.agent_status)) {
      return sendSuccess(res, {
        absence_id:   event._id,
        agent_ref_id: event.agent_ref_id,
        status:       event.agent_status,
        ai_decision:  event.ai_decision,
        event,
      }, "Absence decision fetched");
    }

    if (!event.agent_ref_id) {
      return sendError(res, "No agent_ref_id — this absence was not submitted to the AI agent", 400);
    }

    const agentResult = await getAbsenceDecision(event.agent_ref_id);
    await syncAbsenceDecision(oid, agentResult);

    const updated = await AbsenceEvent.findById(oid);
    return sendSuccess(
      res,
      {
        absence_id:   event._id,
        agent_ref_id: event.agent_ref_id,
        status:       agentResult.status,
        ai_decision:  agentResult.absence?.ai_decision,
        agent_result: agentResult,
        event:        updated,
      },
      "Absence decision fetched"
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getAllAbsenceEvents = async (req, res) => {
  try {
    const { status, employee_id, escalation_required, limit = 50, skip = 0 } = req.query;
    const filter = {};
    if (status)      filter.status      = status;
    if (employee_id) filter.employee_id = employee_id;
    if (escalation_required !== undefined)
      filter.escalation_required = escalation_required === "true";

    const [events, total] = await Promise.all([
      AbsenceEvent.find(filter)
        .populate("employee_id")
        .sort({ unexcused_count_90d: -1, created_at: 1 })
        .skip(Number(skip))
        .limit(Number(limit)),
      AbsenceEvent.countDocuments(filter),
    ]);

    return sendSuccess(res, { events, total }, "Absence events fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getPendingAbsenceEvents = async (req, res) => {
  try {
    const events = await AbsenceEvent.find({ status: "pending" })
      .populate("employee_id")
      .sort({ unexcused_count_90d: -1, created_at: 1 });
    return sendSuccess(res, events, "Pending absence events fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getAbsenceEventById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const event = await AbsenceEvent.findById(oid).populate("employee_id");
    if (!event) return sendError(res, "Absence event not found", 404);

    return sendSuccess(res, event, "Absence event fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getEmployeeAbsences = async (req, res) => {
  try {
    const { employee_id } = req.params;
    const limit = Number(req.query.limit) || 50;

    const absences = await AbsenceEvent.find({ employee_id })
      .populate("employee_id")
      .sort({ absence_date: -1 })
      .limit(limit);

    const cutoff = new Date(Date.now() - 90 * 86_400_000);
    const unexcused_count = await AbsenceEvent.countDocuments({
      employee_id,
      absence_type_claimed: { $in: ["unexcused", "غياب بدون إذن"] },
      created_at:           { $gte: cutoff },
      status:               { $nin: ["pending", "cancelled"] },
    });

    return sendSuccess(res, { absences, unexcused_count_90d: unexcused_count }, "Employee absences fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const updateAbsenceEventStatus = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const {
      status, ai_decision = "", ai_classification = "",
      confidence_score = 0, decision_reason = "",
      payroll_deduction_days = 0, escalation_required = false, request_id = "",
    } = req.body;

    const updated = await AbsenceEvent.findByIdAndUpdate(
      oid,
      {
        $set: {
          status,
          ai_decision:            ai_decision.substring(0, 100),
          ai_classification:      ai_classification.substring(0, 100),
          confidence_score:       Number(confidence_score),
          decision_reason:        decision_reason.substring(0, 1000),
          payroll_deduction_days: Number(payroll_deduction_days),
          escalation_required:    Boolean(escalation_required),
          request_id:             request_id.substring(0, 100),
        },
      },
      { new: true, runValidators: true }
    );

    if (!updated) return sendError(res, "Absence event not found", 404);
    return sendSuccess(res, updated, "Absence event updated");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const deleteAbsenceEvent = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const deleted = await AbsenceEvent.findByIdAndDelete(oid);
    if (!deleted) return sendError(res, "Absence event not found", 404);

    return sendSuccess(res, [], "Absence event deleted");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  INCENTIVE REQUEST
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /v1/hr/incentive-requests
 * Saves the incentive request locally and returns immediately (202).
 * See createLeave() above for why the old submitIncentiveToAgent()
 * loopback call was removed — same deadlock pattern.
 */
export const createIncentiveRequest = async (req, res) => {
  try {
    const incentive = await IncentiveRequest.create({
      ...req.body,
      agent_status: "pending",
      submitted_at: new Date(),
    });

    return sendSuccess(
      res,
      {
        incentive_id: incentive._id,
        agent_status: "pending",
        decision_url: `/v1/hr/incentive-requests/${incentive._id}/decision`,
        note:         "Saved — background trigger engine will process this automatically",
      },
      "Incentive request submitted",
      202
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};


/**
 * GET /v1/hr/incentive-requests/:id/decision
 */
export const getIncentiveDecisionById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const incentive = await IncentiveRequest.findById(oid);
    if (!incentive) return sendError(res, "Incentive request not found", 404);

    if (incentive.agent_status && !["pending", "processing", "agent_unavailable"].includes(incentive.agent_status)) {
      return sendSuccess(res, {
        incentive_id: incentive._id,
        agent_ref_id: incentive.agent_ref_id,
        status:       incentive.agent_status,
        ai_decision:  incentive.ai_decision,
        incentive,
      }, "Incentive decision fetched");
    }

    if (!incentive.agent_ref_id) {
      return sendError(res, "No agent_ref_id — this incentive was not submitted to the AI agent", 400);
    }

    const agentResult = await getIncentiveDecision(incentive.agent_ref_id);
    await syncIncentiveDecision(oid, agentResult);

    const updated = await IncentiveRequest.findById(oid);
    return sendSuccess(
      res,
      {
        incentive_id: incentive._id,
        agent_ref_id: incentive.agent_ref_id,
        status:       agentResult.status,
        ai_decision:  agentResult.incentive?.ai_decision,
        agent_result: agentResult,
        incentive:    updated,
      },
      "Incentive decision fetched"
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getAllIncentiveRequests = async (req, res) => {
  try {
    const { status, employee_id, incentive_type, limit = 20, skip = 0 } = req.query;
    const filter = {};
    if (status)         filter.status         = status;
    if (employee_id)    filter.employee_id    = employee_id;
    if (incentive_type) filter.incentive_type = incentive_type;

    const [incentives, total] = await Promise.all([
      IncentiveRequest.find(filter)
        .populate("employee_id")
        .sort({ incentive_type: 1, created_at: 1 })
        .skip(Number(skip))
        .limit(Number(limit)),
      IncentiveRequest.countDocuments(filter),
    ]);

    return sendSuccess(res, { incentives, total }, "Incentive requests fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getPendingIncentiveRequests = async (req, res) => {
  try {
    const incentives = await IncentiveRequest.find({ status: "pending" })
      .populate("employee_id")
      .sort({ incentive_type: 1, created_at: 1 });
    return sendSuccess(res, incentives, "Pending incentive requests fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getIncentiveRequestById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const incentive = await IncentiveRequest.findById(oid).populate("employee_id");
    if (!incentive) return sendError(res, "Incentive request not found", 404);

    return sendSuccess(res, incentive, "Incentive request fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const updateIncentiveStatus = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const {
      status, ai_decision = "", confidence_score = 0,
      decision_reason = "", approved_amount_egp, request_id = "",
    } = req.body;

    const updated = await IncentiveRequest.findByIdAndUpdate(
      oid,
      {
        $set: {
          status,
          ai_decision:        ai_decision.substring(0, 100),
          confidence_score:   Number(confidence_score),
          decision_reason:    decision_reason.substring(0, 1000),
          approved_amount_egp:approved_amount_egp ?? null,
          request_id:         request_id.substring(0, 100),
        },
      },
      { new: true, runValidators: true }
    );

    if (!updated) return sendError(res, "Incentive request not found", 404);
    return sendSuccess(res, updated, "Incentive request updated");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const deleteIncentiveRequest = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const deleted = await IncentiveRequest.findByIdAndDelete(oid);
    if (!deleted) return sendError(res, "Incentive request not found", 404);

    return sendSuccess(res, [], "Incentive request deleted");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  HR DOMAIN AUDIT
// ══════════════════════════════════════════════════════════════════════════════

export const createHRAuditEntry = async (req, res) => {
  try {
    const entry = await HRDomainAudit.create(req.body);
    return sendSuccess(res, entry, "HR audit entry created", 201);
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getHRAuditByEntity = async (req, res) => {
  try {
    const { domain, entity_id } = req.params;
    const oid = resolveOid(res, entity_id);
    if (!oid) return;

    const limit = Number(req.query.limit) || 50;
    const entries = await HRDomainAudit.find({ domain, entity_id: oid })
      .populate("employee_id")
      .sort({ created_at: -1 })
      .limit(limit);

    return sendSuccess(res, entries, "HR audit entries fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  BALANCE AUDIT LOG
// ══════════════════════════════════════════════════════════════════════════════

export const createBalanceAuditEntry = async (req, res) => {
  try {
    const { employee_id, old_balance, new_balance, change_reason, leave_id, performed_by } = req.body;

    const delta = Number(new_balance) - Number(old_balance);
    const isAllowedIncrease = ["reset", "correction", "carryover"].some((kw) =>
      String(change_reason).toLowerCase().includes(kw)
    );
    if (delta > 0 && !isAllowedIncrease) {
      console.warn(
        `⚠️ [BalanceAudit] Unexpected INCREASE: employee=${employee_id} | ${old_balance}→${new_balance} (+${delta}) | reason=${change_reason}`
      );
    }

    const entry = await BalanceAuditLog.create({
      employee_id,
      old_balance:  Number(old_balance),
      new_balance:  Number(new_balance),
      delta,
      change_reason:String(change_reason).substring(0, 300),
      leave_id:     leave_id     || null,
      performed_by: performed_by || "hr_agent",
    });

    return sendSuccess(res, entry, "Balance audit entry created", 201);
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getBalanceHistory = async (req, res) => {
  try {
    const { employee_id } = req.params;
    const limit = Number(req.query.limit) || 20;

    const history = await BalanceAuditLog.find({ employee_id })
      .populate("employee_id")
      .sort({ created_at: -1 })
      .limit(limit);

    return sendSuccess(res, history, "Balance history fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  HR DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════

export const getHRDashboardStats = async (req, res) => {
  try {
    const countByStatus = (Model) =>
      Model.aggregate([{ $group: { _id: "$status", count: { $sum: 1 } } }]).then((docs) =>
        Object.fromEntries(docs.map((d) => [d._id, d.count]))
      );

    const [leaveStats, salaryStats, absenceStats, incentiveStats, escalated, pipCount] =
      await Promise.all([
        countByStatus(Leave),
        countByStatus(SalaryReview),
        countByStatus(AbsenceEvent),
        countByStatus(IncentiveRequest),
        AbsenceEvent.countDocuments({ escalation_required: true }),
        AbsenceEvent.aggregate([
          { $match: { status: "pending" } },
          { $lookup: { from: "employees", localField: "employee_id", foreignField: "_id", as: "_emp" } },
          { $unwind: "$_emp" },
          { $match: { "_emp.is_on_pip": true } },
          { $count: "count" },
        ]).then((r) => r[0]?.count || 0),
      ]);

    return sendSuccess(
      res,
      {
        leaves:         leaveStats,
        salary_reviews: salaryStats,
        absence_events: absenceStats,
        incentives:     incentiveStats,
        alerts: {
          escalation_required:   escalated,
          pip_employees_pending: pipCount,
        },
        generated_at: new Date().toISOString(),
      },
      "HR dashboard stats fetched"
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};