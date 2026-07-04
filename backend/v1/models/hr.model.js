/**
 * models/hr.model.js — HR Mongoose Models
 * =========================================
 * Collections:
 *   • Leave             — Leave requests + AI decisions
 *   • SalaryReview      — Salary review requests + AI decisions
 *   • AbsenceEvent      — Absence records + AI classification
 *   • IncentiveRequest  — Incentive/bonus requests + AI decisions
 *   • HRDomainAudit     — Unified HR audit trail (all 4 domains)
 *   • BalanceAuditLog   — Leave balance change history
 *
 * Architecture notes:
 *   • Reusable field-definition objects (employeeRefFields, aiDecisionFields, etc.)
 *     are spread into each schema to eliminate duplication while keeping every
 *     field exactly as documented.
 *   • All schemas reference the "Employee" model for employee_id.
 *   • Department enums are imported from User.js for consistency.
 *
 * Fix log (production-readiness pass):
 *   #1  employee_id: Mixed → ObjectId ref "Employee"
 *   #2  employee_name/department denormalised fields kept but now Optional
 *       and clearly marked as snapshot-at-submission (not live data)
 *   #3  JOB_LEVELS extracted as shared exported constant
 *   #4  department enum aligned with VALID_USER_DEPARTMENTS from User.js
 *   #5  Added missing indexes: SalaryReview, IncentiveRequest, BalanceAuditLog, HRDomainAudit
 *   #6  BalanceAuditLog delta moved to controller; pre('save') kept as safety net only;
 *       pre('findOneAndUpdate') added so PATCH paths also stay correct
 *   #7  employee_id index added to BalanceAuditLog
 *   #8  leave_balance: type changed to Number with integer validation note
 *   #9  Arabic enum value "غياب بدون إذن" replaced with "unexcused_no_permission"
 *   #10 HRDomainAudit.decision_source default changed from "llm" → "rule"
 *       (safest/most common default; overridden by agent when LLM is actually used)
 *   #11 TTL indexes added on hr_domain_audit (365 days) and balance_audit_log (730 days)
 *   #12 Duplicate sparse index on Leave.request_id removed from field definition;
 *       kept only in the explicit .index() call
 *   #13 Extracted repeated field patterns into reusable objects to eliminate 4× duplication
 */

import mongoose from "mongoose";
import { VALID_USER_DEPARTMENTS } from "./User.js";


// ══════════════════════════════════════════════════════════════════════════════
//  SHARED CONSTANTS
// ══════════════════════════════════════════════════════════════════════════════

export const JOB_LEVELS = [
  "junior", "mid", "senior", "lead", "manager", "director", "c_level",
];

export const HR_DECISION_STATUSES = ["pending", "in_progress", "approved", "rejected", "escalated", "cancelled"];
export const DECISION_SOURCES     = ["ml", "llm", "rule", ""];

export const ABSENCE_STATUSES       = ["pending", "excused", "unexcused", "escalated", "cancelled"];
export const ABSENCE_TYPES_CLAIMED  = ["unexcused", "unexcused_no_permission", "medical", "emergency", "approved_late", "other"];
export const WARNING_LEVELS         = ["none", "verbal", "written_1st", "written_2nd", "final"];
export const LEAVE_TYPES            = ["annual", "sick", "emergency", "unpaid", "maternity", "paternity", "other"];
export const APPRAISAL_CYCLES       = ["Annual", "Semi-Annual", "Quarterly", "Ad-hoc"];
export const INCENTIVE_TYPES        = ["performance_bonus", "retention_bonus", "project_bonus", "annual_bonus", "spot_award", "other"];
export const PERF_TRENDS            = ["improving", "stable", "declining"];
export const HR_AUDIT_DOMAINS       = ["leave", "salary", "absence", "incentive"];


// ══════════════════════════════════════════════════════════════════════════════
//  SHARED SCHEMA OPTIONS
// ══════════════════════════════════════════════════════════════════════════════

/** Timestamps with snake_case aliases — used by all HR domain schemas */
const TIMESTAMPS_FULL  = { timestamps: { createdAt: "created_at", updatedAt: "updated_at" } };
/** Timestamps with created_at only (immutable audit records) */
const TIMESTAMPS_AUDIT = { timestamps: { createdAt: "created_at", updatedAt: false } };

/** Department enum that allows empty string for legacy records */
const DEPARTMENTS_WITH_EMPTY = [...VALID_USER_DEPARTMENTS, ""];


// ══════════════════════════════════════════════════════════════════════════════
//  REUSABLE FIELD DEFINITIONS  (fix #13 — were duplicated 4× inline)
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Employee reference fields — every HR domain entity links to an Employee.
 * employee_name & department are submission-time snapshots (denormalised
 * intentionally). Always join to Employee for current/live values.
 */
const employeeRefFields = {
  employee_id: {
    type:     mongoose.Schema.Types.ObjectId,
    ref:      "Employee",
    required: true,
    index:    true,
  },
  employee_name: { type: String, default: "", trim: true },
  department: {
    type:    String,
    default: "",
    trim:    true,
    enum:    DEPARTMENTS_WITH_EMPTY,
  },
};

/** Job level field — used by SalaryReview, AbsenceEvent, IncentiveRequest */
const jobLevelField = {
  job_level: {
    type:    String,
    default: "junior",
    enum:    JOB_LEVELS,
  },
};

/**
 * Core AI decision fields — shared across all 4 HR domain schemas.
 * Domain-specific AI fields (e.g. ai_classification, recommended_increment_pct)
 * are added inline within each schema.
 */
const aiDecisionFields = {
  ai_decision:      { type: String,  default: "",  maxlength: 100 },
  confidence_score: { type: Number,  default: 0.0, min: 0, max: 1 },
  decision_reason:  { type: String,  default: "",  maxlength: 1000 },
  request_id:       { type: String,  default: "",  maxlength: 100 },
  notes:            { type: String,  default: "",  maxlength: 500 },
};

/** Standard HR status field — used by Leave, SalaryReview, IncentiveRequest */
const hrStatusField = {
  status: {
    type:    String,
    default: "pending",
    enum:    HR_DECISION_STATUSES,
    index:   true,
  },
};


// ══════════════════════════════════════════════════════════════════════════════
//  LEAVE
// ══════════════════════════════════════════════════════════════════════════════

const leaveSchema = new mongoose.Schema(
  {
    ...employeeRefFields,

    leave_type: {
      type:    String,
      default: "annual",
      enum:    LEAVE_TYPES,
      index:   true,
    },
    leave_days: { type: Number, default: 1, min: 0 },
    reason:     { type: String, default: "", trim: true },
    leave_balance: {
      type:    Number,
      default: 0,
      min:     0,
      validate: {
        validator: (v) => Number.isInteger(v),
        message:   "leave_balance must be a whole number (integer days)",
      },
    },

    ...hrStatusField,

    // AI Decision — core + leave-specific extras
    ...aiDecisionFields,
    decision_source: {
      type:    String,
      default: "",
      enum:    DECISION_SOURCES,
    },
    tier:     { type: Number,  default: 2,     enum: [1, 2, 3] },
    llm_used: { type: Boolean, default: false },
  },
  {
    ...TIMESTAMPS_FULL,
    collection: "leaves",
  }
);

leaveSchema.index({ status: 1, created_at: -1 });
leaveSchema.index({ employee_id: 1, created_at: -1 });
leaveSchema.index({ request_id: 1 }, { sparse: true });

export const Leave = mongoose.model("Leave", leaveSchema);


// ══════════════════════════════════════════════════════════════════════════════
//  SALARY REVIEW
// ══════════════════════════════════════════════════════════════════════════════

const salaryReviewSchema = new mongoose.Schema(
  {
    ...employeeRefFields,
    ...jobLevelField,

    salary_grade: { type: String, default: "C", maxlength: 10 },

    current_salary_egp:          { type: Number, default: 0,    min: 0 },
    requested_increment_pct:     { type: Number, default: 0.10, min: 0, max: 1 },
    market_median_egp:           { type: Number, default: 0,    min: 0 },
    market_gap_pct:              { type: Number, default: 0 },
    months_since_last_increment: { type: Number, default: 12,   min: 0 },
    months_in_role:              { type: Number, default: 0,    min: 0 },
    appraisal_cycle: {
      type:    String,
      default: "Annual",
      enum:    APPRAISAL_CYCLES,
    },
    kpi_achievement:    { type: Number,  default: 0.80, min: 0, max: 1 },
    budget_utilization: { type: Number,  default: 0.80, min: 0, max: 1 },
    available_pool_egp: { type: Number,  default: 0,    min: 0 },
    is_on_pip:          { type: Boolean, default: false },
    is_on_probation:    { type: Boolean, default: false },

    ...hrStatusField,

    // AI Decision — core + salary-specific extras
    ...aiDecisionFields,
    recommended_increment_pct: { type: Number, default: null },
  },
  {
    ...TIMESTAMPS_FULL,
    collection: "salary_reviews",
  }
);

salaryReviewSchema.index({ status: 1, created_at: -1 });
salaryReviewSchema.index({ employee_id: 1, created_at: -1 });
salaryReviewSchema.index({ request_id: 1 }, { sparse: true });

export const SalaryReview = mongoose.model("SalaryReview", salaryReviewSchema);


// ══════════════════════════════════════════════════════════════════════════════
//  ABSENCE EVENT
// ══════════════════════════════════════════════════════════════════════════════

const absenceEventSchema = new mongoose.Schema(
  {
    ...employeeRefFields,
    ...jobLevelField,

    leave_balance: { type: Number, default: 0 },

    absence_date: { type: Date, required: true, index: true },

    absence_type_claimed: {
      type:    String,
      default: "unexcused",
      enum:    ABSENCE_TYPES_CLAIMED,
    },
    duration_hours:               { type: Number,  default: 8,     min: 0 },
    medical_certificate_provided: { type: Boolean, default: false },
    prior_approval_obtained:      { type: Boolean, default: false },
    reason:                       { type: String,  default: "",    trim: true },

    total_absences_90d:  { type: Number, default: 0, min: 0 },
    unexcused_count_90d: { type: Number, default: 0, min: 0, index: true },
    late_arrivals_90d:   { type: Number, default: 0, min: 0 },
    previous_warnings: {
      type:    String,
      default: "none",
      enum:    WARNING_LEVELS,
    },
    performance_score: { type: Number,  default: 0.75, min: 0, max: 1 },
    is_on_pip:         { type: Boolean, default: false },

    // AbsenceEvent uses a DIFFERENT status enum than the other HR domains
    status: {
      type:    String,
      default: "pending",
      enum:    ABSENCE_STATUSES,
      index:   true,
    },

    // AI Decision — core + absence-specific extras
    ...aiDecisionFields,
    ai_classification:      { type: String,  default: "",    maxlength: 100 },
    payroll_deduction_days: { type: Number,  default: 0.0,  min: 0 },
    escalation_required:    { type: Boolean, default: false, index: true },
  },
  {
    ...TIMESTAMPS_FULL,
    collection: "absence_events",
  }
);

absenceEventSchema.index({ employee_id: 1, absence_date: -1 });
absenceEventSchema.index({ unexcused_count_90d: -1, created_at: 1 });

export const AbsenceEvent = mongoose.model("AbsenceEvent", absenceEventSchema);


// ══════════════════════════════════════════════════════════════════════════════
//  INCENTIVE REQUEST
// ══════════════════════════════════════════════════════════════════════════════

const incentiveRequestSchema = new mongoose.Schema(
  {
    ...employeeRefFields,
    ...jobLevelField,

    incentive_type: {
      type:    String,
      default: "performance_bonus",
      enum:    INCENTIVE_TYPES,
      index:   true,
    },
    requested_amount_egp:           { type: Number,  default: 0,    min: 0 },
    approved_amount_egp:            { type: Number,  default: null },
    kpi_achievement:                { type: Number,  default: 0.80, min: 0, max: 1 },
    performance_score:              { type: Number,  default: 0.75, min: 0, max: 1 },
    monthly_salary_egp:             { type: Number,  default: 0,    min: 0 },
    tenure_months:                  { type: Number,  default: 0,    min: 0 },
    is_on_pip:                      { type: Boolean, default: false },
    is_critical_talent:             { type: Boolean, default: false },
    incentive_budget_remaining_egp: { type: Number,  default: 0,    min: 0 },
    perf_trend: {
      type:    String,
      default: "stable",
      enum:    PERF_TRENDS,
    },
    reason: { type: String, default: "", trim: true },

    ...hrStatusField,

    // AI Decision — core only (no domain-specific extras for incentive)
    ...aiDecisionFields,
  },
  {
    ...TIMESTAMPS_FULL,
    collection: "incentive_requests",
  }
);

incentiveRequestSchema.index({ status: 1, incentive_type: 1, created_at: 1 });
incentiveRequestSchema.index({ employee_id: 1, created_at: -1 });

export const IncentiveRequest = mongoose.model("IncentiveRequest", incentiveRequestSchema);


// ══════════════════════════════════════════════════════════════════════════════
//  HR DOMAIN AUDIT
// ══════════════════════════════════════════════════════════════════════════════

const hrDomainAuditSchema = new mongoose.Schema(
  {
    domain: {
      type:     String,
      required: true,
      enum:     HR_AUDIT_DOMAINS,
      index:    true,
    },
    entity_id:   { type: mongoose.Schema.Types.ObjectId, required: true, index: true },
    employee_id: { type: mongoose.Schema.Types.ObjectId, ref: "Employee", index: true },
    decision:        { type: String, default: "", maxlength: 100 },
    confidence:      { type: Number, default: 0.0, min: 0, max: 1 },
    decision_source: {
      type:    String,
      default: "rule",
      enum:    ["ml", "llm", "rule"],
    },
    override_rule: { type: String,  default: "" },
    llm_used:      { type: Boolean, default: false },
    execution_ms:  { type: Number,  default: 0, min: 0 },
    request_id:    { type: String,  default: "", maxlength: 100 },
    flags:         { type: [String], default: [] },
    extra_data:    { type: mongoose.Schema.Types.Mixed, default: {} },
  },
  {
    ...TIMESTAMPS_AUDIT,
    collection: "hr_domain_audit",
  }
);

hrDomainAuditSchema.index({ domain: 1, entity_id: 1 });
hrDomainAuditSchema.index({ created_at: -1 });
// TTL: auto-delete audit entries after 365 days
hrDomainAuditSchema.index({ created_at: 1 }, { expireAfterSeconds: 365 * 24 * 60 * 60 });

export const HRDomainAudit = mongoose.model("HRDomainAudit", hrDomainAuditSchema);


// ══════════════════════════════════════════════════════════════════════════════
//  BALANCE AUDIT LOG
// ══════════════════════════════════════════════════════════════════════════════

const balanceAuditLogSchema = new mongoose.Schema(
  {
    employee_id: {
      type:     mongoose.Schema.Types.ObjectId,
      ref:      "Employee",
      required: true,
      index:    true,
    },
    leave_id:      { type: mongoose.Schema.Types.ObjectId, default: null, index: true, sparse: true },
    old_balance:   { type: Number, required: true },
    new_balance:   { type: Number, required: true },
    delta:         { type: Number, required: true },
    change_reason: { type: String, required: true, maxlength: 300 },
    performed_by:  { type: String, default: "hr_agent" },
  },
  {
    ...TIMESTAMPS_AUDIT,
    collection: "balance_audit_log",
  }
);

// Safety net for .save() path — delta should be set in controller before .create()
balanceAuditLogSchema.pre("save", function () {
  this.delta = this.new_balance - this.old_balance;
});

// Safety net for findOneAndUpdate / findByIdAndUpdate paths
balanceAuditLogSchema.pre("findOneAndUpdate", function () {
  const update = this.getUpdate();
  const set = update?.$set ?? update ?? {};
  if (set.new_balance !== undefined && set.old_balance !== undefined) {
    const target = update.$set ?? update;
    target.delta = set.new_balance - set.old_balance;
  }
});

balanceAuditLogSchema.index({ employee_id: 1, created_at: -1 });
// TTL: auto-delete balance log after 730 days (2 years for payroll compliance)
balanceAuditLogSchema.index({ created_at: 1 }, { expireAfterSeconds: 730 * 24 * 60 * 60 });

export const BalanceAuditLog = mongoose.model("BalanceAuditLog", balanceAuditLogSchema);