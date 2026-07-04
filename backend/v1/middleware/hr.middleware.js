/**
 * middleware/hr.middleware.js — HR Validation Middleware
 * ========================================================
 * Covers: Leave / SalaryReview / AbsenceEvent / IncentiveRequest
 *         + AI status update bodies + Balance audit
 *
 * Stack: express-validator
 *
 * Usage:
 *   import { validateCreateLeave, validationHandler } from "../middleware/hr.middleware.js";
 *   router.post("/", validateCreateLeave, validationHandler, createLeave);
 */

import { body, param, query, validationResult } from "express-validator";
import { JOB_LEVELS, HR_DECISION_STATUSES, DECISION_SOURCES } from "../models/hr.model.js";
import { VALID_USER_DEPARTMENTS } from "../models/User.js";

// ── Shared handler ─────────────────────────────────────────────────────────

export const validationHandler = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({
      status:  "failed",
      data:    errors.array(),
      message: "Validation error",
    });
  }
  next();
};

// ── Shared field rules ─────────────────────────────────────────────────────

// fix #1 — employee_id is now a MongoDB ObjectId (ref: "Employee")
const ruleEmployeeId = () =>
  body("employee_id")
    .notEmpty().withMessage("employee_id is required")
    .isMongoId().withMessage("employee_id must be a valid MongoDB ObjectId");

const ruleConfidence = () =>
  body("confidence_score")
    .optional()
    .isFloat({ min: 0, max: 1 }).withMessage("confidence_score must be between 0 and 1");

const ruleAIDecision = () =>
  body("ai_decision")
    .optional()
    .isString()
    .isLength({ max: 100 }).withMessage("ai_decision max 100 chars");

const ruleDecisionReason = () =>
  body("decision_reason")
    .optional()
    .isString()
    .isLength({ max: 1000 }).withMessage("decision_reason max 1000 chars");

const ruleRequestId = () =>
  body("request_id")
    .optional()
    .isString()
    .isLength({ max: 100 });

const ruleMongoId = (field = "id") =>
  param(field).isMongoId().withMessage(`${field} must be a valid MongoDB ObjectId`);

// fix #4 — department validated against the same enum as User.js
const ruleDepartment = () =>
  body("department")
    .optional()
    .isString()
    .trim()
    .isIn([...VALID_USER_DEPARTMENTS, ""])
    .withMessage(`department must be one of: ${VALID_USER_DEPARTMENTS.join(", ")}`);

// fix #3 — single source of truth from hr.model.js shared constant
const ruleJobLevel = () =>
  body("job_level")
    .optional()
    .isIn(JOB_LEVELS)
    .withMessage(`job_level must be one of: ${JOB_LEVELS.join(", ")}`);


// ══════════════════════════════════════════════════════════════════════════════
//  LEAVE
// ══════════════════════════════════════════════════════════════════════════════

export const validateCreateLeave = [
  ruleEmployeeId(),

  body("employee_name")
    .optional().isString().trim(),

  ruleDepartment(),

  body("leave_type")
    .optional()
    .isIn(["annual", "sick", "emergency", "unpaid", "maternity", "paternity", "other"])
    .withMessage("Invalid leave_type"),

  body("leave_days")
    .notEmpty().withMessage("leave_days is required")
    .isInt({ min: 1 }).withMessage("leave_days must be a positive integer"),

  body("reason")
    .optional().isString().trim()
    .isLength({ max: 1000 }).withMessage("reason max 1000 chars"),

  // fix #8 — consistent integer validation matching the schema validator
  body("leave_balance")
    .optional()
    .isInt({ min: 0 }).withMessage("leave_balance must be a non-negative integer"),

  body("status")
    .optional()
    .isIn(HR_DECISION_STATUSES)
    .withMessage("Invalid status"),
];

export const validateUpdateLeaveStatus = [
  ruleMongoId(),

  body("status")
    .notEmpty().withMessage("status is required")
    .isIn(HR_DECISION_STATUSES)
    .withMessage("Invalid status"),

  ruleAIDecision(),
  ruleConfidence(),
  ruleDecisionReason(),

  body("decision_source")
    .optional()
    .isIn(DECISION_SOURCES)
    .withMessage(`decision_source must be one of: ${DECISION_SOURCES.filter(Boolean).join(" | ")}`),

  body("tier")
    .optional()
    .isInt({ min: 1, max: 3 }).withMessage("tier must be 1, 2, or 3"),

  body("llm_used")
    .optional().isBoolean(),

  ruleRequestId(),

  body("notes")
    .optional().isString().isLength({ max: 500 }),
];


// ══════════════════════════════════════════════════════════════════════════════
//  SALARY REVIEW
// ══════════════════════════════════════════════════════════════════════════════

export const validateCreateSalaryReview = [
  ruleEmployeeId(),

  body("employee_name").optional().isString().trim(),
  ruleDepartment(),
  ruleJobLevel(),

  body("salary_grade")
    .optional().isString().isLength({ max: 10 }),

  body("current_salary_egp")
    .notEmpty().withMessage("current_salary_egp is required")
    .isFloat({ min: 0 }).withMessage("current_salary_egp must be ≥ 0"),

  body("requested_increment_pct")
    .optional()
    .isFloat({ min: 0, max: 1 }).withMessage("requested_increment_pct must be between 0 and 1"),

  body("market_median_egp")
    .optional()
    .isFloat({ min: 0 }),

  body("market_gap_pct")
    .optional()
    .isFloat(),

  body("months_since_last_increment")
    .optional()
    .isInt({ min: 0 }),

  body("months_in_role")
    .optional()
    .isInt({ min: 0 }),

  body("appraisal_cycle")
    .optional()
    .isIn(["Annual", "Semi-Annual", "Quarterly", "Ad-hoc"])
    .withMessage("Invalid appraisal_cycle"),

  body("kpi_achievement")
    .optional()
    .isFloat({ min: 0, max: 1 }).withMessage("kpi_achievement must be between 0 and 1"),

  body("budget_utilization")
    .optional()
    .isFloat({ min: 0, max: 1 }),

  body("available_pool_egp")
    .optional()
    .isFloat({ min: 0 }),

  body("is_on_pip").optional().isBoolean(),
  body("is_on_probation").optional().isBoolean(),

  body("status")
    .optional()
    .isIn(HR_DECISION_STATUSES),
];

export const validateUpdateSalaryReviewStatus = [
  ruleMongoId(),

  body("status")
    .notEmpty().withMessage("status is required")
    .isIn(HR_DECISION_STATUSES)
    .withMessage("Invalid status"),

  ruleAIDecision(),
  ruleConfidence(),
  ruleDecisionReason(),

  body("recommended_increment_pct")
    .optional()
    .isFloat({ min: 0, max: 1 }).withMessage("recommended_increment_pct must be between 0 and 1"),

  ruleRequestId(),
];


// ══════════════════════════════════════════════════════════════════════════════
//  ABSENCE EVENT
// ══════════════════════════════════════════════════════════════════════════════

export const validateCreateAbsenceEvent = [
  ruleEmployeeId(),

  body("employee_name").optional().isString().trim(),
  ruleDepartment(),
  ruleJobLevel(),

  body("leave_balance")
    .optional()
    .isInt(),

  body("absence_date")
    .notEmpty().withMessage("absence_date is required")
    .isISO8601().withMessage("absence_date must be a valid ISO 8601 date"),

  // fix #9 — Arabic value replaced; validate against updated enum
  body("absence_type_claimed")
    .optional()
    .isIn(["unexcused", "unexcused_no_permission", "medical", "emergency", "approved_late", "other"])
    .withMessage("Invalid absence_type_claimed"),

  body("duration_hours")
    .optional()
    .isFloat({ min: 0 }).withMessage("duration_hours must be ≥ 0"),

  body("medical_certificate_provided").optional().isBoolean(),
  body("prior_approval_obtained").optional().isBoolean(),

  body("reason").optional().isString().trim(),

  body("total_absences_90d")
    .optional()
    .isInt({ min: 0 }),

  body("unexcused_count_90d")
    .optional()
    .isInt({ min: 0 }),

  body("late_arrivals_90d")
    .optional()
    .isInt({ min: 0 }),

  body("previous_warnings")
    .optional()
    .isIn(["none", "verbal", "written_1st", "written_2nd", "final"])
    .withMessage("Invalid previous_warnings value"),

  body("performance_score")
    .optional()
    .isFloat({ min: 0, max: 1 }),

  body("is_on_pip").optional().isBoolean(),

  body("status")
    .optional()
    .isIn(["pending", "excused", "unexcused", "escalated", "cancelled"]),
];

export const validateUpdateAbsenceEventStatus = [
  ruleMongoId(),

  body("status")
    .notEmpty().withMessage("status is required")
    .isIn(["pending", "excused", "unexcused", "escalated", "cancelled"])
    .withMessage("Invalid status"),

  ruleAIDecision(),

  body("ai_classification")
    .optional()
    .isString()
    .isLength({ max: 100 }),

  ruleConfidence(),
  ruleDecisionReason(),

  body("payroll_deduction_days")
    .optional()
    .isFloat({ min: 0 }).withMessage("payroll_deduction_days must be ≥ 0"),

  body("escalation_required")
    .optional()
    .isBoolean(),

  ruleRequestId(),
];


// ══════════════════════════════════════════════════════════════════════════════
//  INCENTIVE REQUEST
// ══════════════════════════════════════════════════════════════════════════════

export const validateCreateIncentiveRequest = [
  ruleEmployeeId(),

  body("employee_name").optional().isString().trim(),
  ruleDepartment(),
  ruleJobLevel(),

  body("incentive_type")
    .optional()
    .isIn(["performance_bonus", "retention_bonus", "project_bonus", "annual_bonus", "spot_award", "other"])
    .withMessage("Invalid incentive_type"),

  body("requested_amount_egp")
    .notEmpty().withMessage("requested_amount_egp is required")
    .isFloat({ min: 0 }).withMessage("requested_amount_egp must be ≥ 0"),

  body("kpi_achievement")
    .optional()
    .isFloat({ min: 0, max: 1 }),

  body("performance_score")
    .optional()
    .isFloat({ min: 0, max: 1 }),

  body("monthly_salary_egp")
    .optional()
    .isFloat({ min: 0 }),

  body("tenure_months")
    .optional()
    .isInt({ min: 0 }),

  body("is_on_pip").optional().isBoolean(),
  body("is_critical_talent").optional().isBoolean(),

  body("incentive_budget_remaining_egp")
    .optional()
    .isFloat({ min: 0 }),

  body("perf_trend")
    .optional()
    .isIn(["improving", "stable", "declining"])
    .withMessage("perf_trend must be improving | stable | declining"),

  body("reason").optional().isString().trim(),

  body("status")
    .optional()
    .isIn(HR_DECISION_STATUSES),
];

export const validateUpdateIncentiveStatus = [
  ruleMongoId(),

  body("status")
    .notEmpty().withMessage("status is required")
    .isIn(HR_DECISION_STATUSES)
    .withMessage("Invalid status"),

  ruleAIDecision(),
  ruleConfidence(),
  ruleDecisionReason(),

  body("approved_amount_egp")
    .optional()
    .isFloat({ min: 0 }).withMessage("approved_amount_egp must be ≥ 0"),

  ruleRequestId(),
];


// ══════════════════════════════════════════════════════════════════════════════
//  BALANCE AUDIT LOG
// ══════════════════════════════════════════════════════════════════════════════

export const validateCreateBalanceAudit = [
  // fix #1 — employee_id is now ObjectId
  body("employee_id")
    .notEmpty().withMessage("employee_id is required")
    .isMongoId().withMessage("employee_id must be a valid MongoDB ObjectId"),

  body("old_balance")
    .notEmpty().withMessage("old_balance is required")
    .isInt().withMessage("old_balance must be an integer"),

  body("new_balance")
    .notEmpty().withMessage("new_balance is required")
    .isInt().withMessage("new_balance must be an integer"),

  body("change_reason")
    .notEmpty().withMessage("change_reason is required")
    .isString()
    .isLength({ max: 300 }).withMessage("change_reason max 300 chars"),

  body("leave_id")
    .optional()
    .isMongoId().withMessage("leave_id must be a valid MongoDB ObjectId"),

  body("performed_by")
    .optional()
    .isString(),
];


// ══════════════════════════════════════════════════════════════════════════════
//  SHARED QUERY VALIDATORS (for GET list endpoints)
// ══════════════════════════════════════════════════════════════════════════════

export const validateListQuery = [
  query("limit")
    .optional()
    .isInt({ min: 1, max: 200 }).withMessage("limit must be between 1 and 200"),

  query("skip")
    .optional()
    .isInt({ min: 0 }).withMessage("skip must be ≥ 0"),
];