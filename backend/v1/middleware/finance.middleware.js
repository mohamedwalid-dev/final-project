/**
 * middleware/finance.middleware.js — Finance Validation Middleware
 * =================================================================
 * Covers: Customer / FinanceInvoice / FinanceDecision / FinanceAudit /
 *         FinanceCollectionLog / LegalCase
 *         + AI status update bodies + escalation
 *
 * Stack: express-validator
 *
 * Usage:
 *   import { validateCreateInvoice, validationHandler } from "../middleware/finance.middleware.js";
 *   router.post("/invoices", validateCreateInvoice, validationHandler, createInvoice);
 */

import { body, param, query, validationResult } from "express-validator";
import {
  INVOICE_STATUSES,
  COLLECTION_STRATEGIES,
  SERVICE_STATUSES,
  ACTION_TYPES,
  PRIORITIES,
  LOG_STATUSES,
  CASE_STATUSES,
} from "../models/finance.model.js";

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

// ── Shared rules ───────────────────────────────────────────────────────────

const ruleMongoId = (field = "id") =>
  param(field).isMongoId().withMessage(`${field} must be a valid MongoDB ObjectId`);

const ruleConfidence = () =>
  body("confidence")
    .optional()
    .isFloat({ min: 0, max: 1 }).withMessage("confidence must be between 0 and 1");

const ruleRiskScore = () =>
  body("risk_score")
    .optional()
    .isFloat({ min: 0, max: 1 }).withMessage("risk_score must be between 0 and 1");

const ruleRequestId = () =>
  body("request_id")
    .optional()
    .isString()
    .isLength({ max: 100 });


// ══════════════════════════════════════════════════════════════════════════════
//  CUSTOMER
// ══════════════════════════════════════════════════════════════════════════════

export const validateCreateCustomer = [
  body("name")
    .notEmpty().withMessage("name is required")
    .isString().trim(),

  body("email")
    .notEmpty().withMessage("email is required")
    .isEmail().withMessage("Invalid email format")
    .normalizeEmail(),

  body("phone")
    .optional()
    .isString().trim(),

  body("credit_score")
    .optional()
    .isFloat({ min: 0, max: 1000 }).withMessage("credit_score must be between 0 and 1000"),

  body("industry")
    .optional()
    .isString().trim(),

  body("account_age_months")
    .optional()
    .isInt({ min: 0 }).withMessage("account_age_months must be ≥ 0"),

  body("service_status")
    .optional()
    .isIn(SERVICE_STATUSES)
    .withMessage(`service_status must be one of: ${SERVICE_STATUSES.join(", ")}`),

  body("is_blacklisted")
    .optional()
    .isBoolean(),
];

export const validateUpdateCustomer = [
  ruleMongoId(),

  body("name").optional().isString().trim(),
  body("email").optional().isEmail().normalizeEmail(),
  body("phone").optional().isString().trim(),

  body("credit_score")
    .optional()
    .isFloat({ min: 0, max: 1000 }),

  body("service_status")
    .optional()
    .isIn(SERVICE_STATUSES)
    .withMessage(`service_status must be one of: ${SERVICE_STATUSES.join(", ")}`),

  body("is_blacklisted").optional().isBoolean(),
  body("suspension_reason").optional().isString(),
];


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE INVOICE  (collection: finance_invoices)
// ══════════════════════════════════════════════════════════════════════════════

export const validateCreateInvoice = [
  body("customer_id")
    .notEmpty().withMessage("customer_id is required")
    .isMongoId().withMessage("customer_id must be a valid MongoDB ObjectId"),

  body("amount")
    .notEmpty().withMessage("amount is required")
    .isFloat({ min: 0 }).withMessage("amount must be ≥ 0"),

  body("due_date")
    .notEmpty().withMessage("due_date is required")
    .isISO8601().withMessage("due_date must be a valid ISO 8601 date"),

  body("description")
    .optional()
    .isString().trim(),

  body("status")
    .optional()
    .isIn(INVOICE_STATUSES)
    .withMessage(`status must be one of: ${INVOICE_STATUSES.join(", ")}`),

  body("collection_strategy")
    .optional()
    .isIn(COLLECTION_STRATEGIES)
    .withMessage(`collection_strategy must be one of: ${COLLECTION_STRATEGIES.join(", ")}`),

  body("first_reminder_days")
    .optional()
    .isInt({ min: 0 }).withMessage("first_reminder_days must be ≥ 0"),
];

export const validateUpdateInvoiceStatus = [
  ruleMongoId(),

  body("status")
    .notEmpty().withMessage("status is required")
    .isIn(INVOICE_STATUSES)
    .withMessage(`status must be one of: ${INVOICE_STATUSES.join(", ")}`),

  body("ai_decision")
    .optional()
    .isString()
    .isLength({ max: 100 }),

  ruleRiskScore(),

  body("decision_reason")
    .optional()
    .isString()
    .isLength({ max: 1000 }),

  body("action_plan")
    .optional()
    .isString()
    .isLength({ max: 500 }),

  ruleRequestId(),
];

export const validateUpdateCollectionStrategy = [
  ruleMongoId(),

  body("risk_score")
    .notEmpty().withMessage("risk_score is required")
    .isFloat({ min: 0, max: 1 }).withMessage("risk_score must be between 0 and 1"),

  body("collection_strategy")
    .notEmpty().withMessage("collection_strategy is required")
    .isIn(COLLECTION_STRATEGIES)
    .withMessage(`collection_strategy must be one of: ${COLLECTION_STRATEGIES.join(", ")}`),

  body("first_reminder_days")
    .notEmpty().withMessage("first_reminder_days is required")
    .isInt({ min: 0 }).withMessage("first_reminder_days must be ≥ 0"),

  ruleRequestId(),
];


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE DECISION
// ══════════════════════════════════════════════════════════════════════════════

export const validateSaveFinanceDecision = [
  body("entity_id")
    .notEmpty().withMessage("entity_id is required")
    .isMongoId().withMessage("entity_id must be a valid MongoDB ObjectId"),

  body("entity")
    .optional()
    .isString(),

  body("agent_type")
    .optional()
    .isString(),

  body("decision")
    .notEmpty().withMessage("decision is required")
    .isString()
    .isLength({ max: 100 }),

  ruleConfidence(),
  ruleRiskScore(),

  body("reasoning")
    .optional()
    .isString()
    .isLength({ max: 2000 }),

  body("action_plan")
    .optional()
    .isString()
    .isLength({ max: 1000 }),

  body("execution_ms")
    .optional()
    .isInt({ min: 0 }),

  ruleRequestId(),
];


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE AUDIT
// ══════════════════════════════════════════════════════════════════════════════

export const validateWriteFinanceAudit = [
  body("domain")
    .notEmpty().withMessage("domain is required")
    .isString()
    .isLength({ max: 50 }),

  body("entity_id")
    .notEmpty().withMessage("entity_id is required")
    .isMongoId().withMessage("entity_id must be a valid MongoDB ObjectId"),

  body("customer_id")
    .optional()
    .isMongoId().withMessage("customer_id must be a valid MongoDB ObjectId"),

  body("decision")
    .optional()
    .isString()
    .isLength({ max: 100 }),

  ruleRiskScore(),
  ruleConfidence(),

  body("decision_source")
    .optional()
    .isString()
    .isLength({ max: 100 }),

  body("override_rule")
    .optional()
    .isString()
    .isLength({ max: 100 }),

  body("llm_used").optional().isBoolean(),

  body("execution_ms")
    .optional()
    .isInt({ min: 0 }),

  ruleRequestId(),

  body("action_plan")
    .optional()
    .isArray().withMessage("action_plan must be an array of strings"),

  body("flags")
    .optional()
    .isArray().withMessage("flags must be an array of strings"),
];


// ══════════════════════════════════════════════════════════════════════════════
//  COLLECTION LOG
// ══════════════════════════════════════════════════════════════════════════════

export const validateLogCollectionAction = [
  body("invoice_id")
    .optional()
    .isMongoId().withMessage("invoice_id must be a valid MongoDB ObjectId"),

  body("customer_id")
    .optional()
    .isMongoId().withMessage("customer_id must be a valid MongoDB ObjectId"),

  body("action_type")
    .notEmpty().withMessage("action_type is required")
    .isIn(ACTION_TYPES)
    .withMessage(`action_type must be one of: ${ACTION_TYPES.join(", ")}`),

  body("template_name")
    .optional()
    .isString()
    .isLength({ max: 100 }),

  body("subject")
    .optional()
    .isString()
    .isLength({ max: 300 }),

  body("body")
    .optional()
    .isString()
    .isLength({ max: 5000 }),

  body("priority")
    .optional()
    .isIn(PRIORITIES)
    .withMessage(`priority must be one of: ${PRIORITIES.join(", ")}`),

  body("status")
    .optional()
    .isIn(LOG_STATUSES)
    .withMessage(`status must be one of: ${LOG_STATUSES.join(", ")}`),
];


// ══════════════════════════════════════════════════════════════════════════════
//  LEGAL CASE
// ══════════════════════════════════════════════════════════════════════════════

export const validateCreateLegalCase = [
  body("invoice_id")
    .notEmpty().withMessage("invoice_id is required")
    .isMongoId().withMessage("invoice_id must be a valid MongoDB ObjectId"),

  body("customer_id")
    .optional()
    .isMongoId().withMessage("customer_id must be a valid MongoDB ObjectId"),

  body("case_type")
    .optional()
    .isString()
    .isLength({ max: 100 }),

  body("amount")
    .optional()
    .isFloat({ min: 0 }).withMessage("amount must be ≥ 0"),

  body("priority")
    .optional()
    .isIn(PRIORITIES)
    .withMessage(`priority must be one of: ${PRIORITIES.join(", ")}`),

  body("description")
    .optional()
    .isString()
    .isLength({ max: 2000 }),

  body("sla_days")
    .optional()
    .isInt({ min: 1 }).withMessage("sla_days must be ≥ 1"),

  body("assigned_to")
    .optional()
    .isString(),
];

export const validateUpdateLegalCaseStatus = [
  ruleMongoId(),

  body("status")
    .notEmpty().withMessage("status is required")
    .isIn(CASE_STATUSES)
    .withMessage(`status must be one of: ${CASE_STATUSES.join(", ")}`),

  body("note")
    .optional()
    .isString()
    .isLength({ max: 500 }),

  body("resolution")
    .optional()
    .isString()
    .isLength({ max: 2000 }),
];


// ══════════════════════════════════════════════════════════════════════════════
//  SHARED QUERY VALIDATORS
// ══════════════════════════════════════════════════════════════════════════════

export const validateListQuery = [
  query("limit")
    .optional()
    .isInt({ min: 1, max: 500 }).withMessage("limit must be between 1 and 500"),

  query("skip")
    .optional()
    .isInt({ min: 0 }).withMessage("skip must be ≥ 0"),
];

export const validateOverdueDaysQuery = [
  query("min_days")
    .optional()
    .isInt({ min: 0 }).withMessage("min_days must be ≥ 0"),

  query("limit")
    .optional()
    .isInt({ min: 1, max: 500 }),
];

export const validateCollectionStatsQuery = [
  query("days")
    .optional()
    .isInt({ min: 1, max: 365 }).withMessage("days must be between 1 and 365"),
];