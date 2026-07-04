/**
 * models/finance.model.js — Finance Mongoose Models
 * ====================================================
 * Collections:
 *   • Customer             — Customer profiles
 *   • FinanceInvoice       — AI-powered collection invoices (renamed from Invoice to avoid
 *                            collision with the billing invoiceModel.js in this project)
 *   • FinanceDecision      — AI decision history per invoice
 *   • FinanceAudit         — Finance audit trail
 *   • FinanceCollectionLog — Collection action log
 *   • LegalCase            — Legal escalation cases
 *
 * NOTE: The standalone invoiceModel.js handles client-facing billing invoices (lineItems,
 * tax, currency). This file handles the AI collections domain only.
 */

import mongoose from "mongoose";

// ══════════════════════════════════════════════════════════════════════════════
//  ENUMS (mirrored from finance_models.py)
// ══════════════════════════════════════════════════════════════════════════════

export const INVOICE_STATUSES = [
  "pending", "overdue", "paid", "suspended",
  "legal", "written_off", "cancelled", "payment_plan", "disputed",
];

export const COLLECTION_STRATEGIES = ["standard", "aggressive", "gentle", "legal", "write_off"];
export const SERVICE_STATUSES      = ["active", "suspended", "terminated", "on_hold"];
export const ACTION_TYPES          = [
  "email", "sms", "call_scheduled", "followup_scheduled",
  "legal_escalation", "internal_notification", "system",
  "suspension", "write_off", "payment_plan",
];
export const PRIORITIES    = ["low", "medium", "high", "critical"];
export const LOG_STATUSES  = ["sent", "delivered", "failed", "pending", "cancelled"];
export const CASE_STATUSES = ["opened", "in_progress", "on_hold", "resolved", "settled", "closed"];


// ══════════════════════════════════════════════════════════════════════════════
//  CUSTOMER
// ══════════════════════════════════════════════════════════════════════════════

const customerSchema = new mongoose.Schema(
  {
    name: { type: String, required: true, trim: true },
    email: {
      type: String,
      required: true,
      unique: true,
      trim: true,
      lowercase: true,
      match: [/^[^\s@]+@[^\s@]+\.[^\s@]+$/, "Invalid email format"],
      index: true,
    },
    phone:              { type: String, default: "", trim: true },
    credit_score:       { type: Number, default: 650, min: 0, max: 1000 },
    industry:           { type: String, default: "unknown", trim: true },
    account_age_months: { type: Number, default: 12, min: 0 },
    service_status: {
      type: String,
      default: "active",
      enum: SERVICE_STATUSES,
      index: true,
    },
    suspension_reason: { type: String, default: "" },
    suspended_at:      { type: Date, default: null },
    is_blacklisted:    { type: Boolean, default: false, index: true },
    blacklisted_at:    { type: Date, default: null },
  },
  {
    timestamps: { createdAt: "created_at", updatedAt: "updated_at" },
    collection: "customers",
  }
);

export const Customer = mongoose.model("Customer", customerSchema);


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE INVOICE (renamed from Invoice — avoids collision with invoiceModel.js)
// ══════════════════════════════════════════════════════════════════════════════

const financeInvoiceSchema = new mongoose.Schema(
  {
    customer_id: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Customer",
      required: true,
      index: true,
    },
    amount:      { type: Number, required: true, min: 0 },
    due_date:    { type: Date, required: true, index: true },
    description: { type: String, default: "", trim: true },
    status: {
      type: String,
      default: "pending",
      enum: INVOICE_STATUSES,
      index: true,
    },

    // AI fields
    ai_decision:        { type: String, default: "", maxlength: 100 },
    ai_risk_score:      { type: Number, default: 0.0, min: 0, max: 1, index: true },
    ai_decision_reason: { type: String, default: "", maxlength: 1000 },
    ai_action_plan:     { type: String, default: "", maxlength: 500 },
    ai_request_id:      { type: String, default: "", maxlength: 100 },

    // Collection config
    collection_strategy: {
      type: String,
      default: "standard",
      enum: COLLECTION_STRATEGIES,
    },
    first_reminder_days: { type: Number, default: 7, min: 0 },

    // Lifecycle timestamps
    paid_at:        { type: Date, default: null },
    written_off_at: { type: Date, default: null },
    overdue_days:   { type: Number, default: 0, min: 0 },
  },
  {
    timestamps: { createdAt: "created_at", updatedAt: "updated_at" },
    collection: "finance_invoices",   // separate collection from billing "invoices"
    toJSON: { virtuals: true },
  }
);

// Virtual: real-time overdue calculation
financeInvoiceSchema.virtual("overdue_days_calc").get(function () {
  if (!this.due_date) return 0;
  const diffMs = Date.now() - new Date(this.due_date).getTime();
  return Math.max(0, Math.floor(diffMs / 86_400_000));
});

financeInvoiceSchema.index({ status: 1, due_date: 1 });
financeInvoiceSchema.index({ status: 1, ai_risk_score: 1 });

export const FinanceInvoice = mongoose.model("FinanceInvoice", financeInvoiceSchema);

// Backward-compat alias — lets existing imports of { Invoice } keep working
// during a gradual migration. Remove once all imports are updated.
export { FinanceInvoice as Invoice };


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE DECISION
// ══════════════════════════════════════════════════════════════════════════════

const financeDecisionSchema = new mongoose.Schema(
  {
    agent_type: { type: String, default: "finance_agent" },
    entity:     { type: String, default: "finance_invoices" },
    entity_id: {
      type: mongoose.Schema.Types.ObjectId,
      required: true,
      index: true,
    },
    event_id:     { type: String, default: null },
    decision:     { type: String, default: "", maxlength: 100 },
    confidence:   { type: Number, default: 0, min: 0, max: 1 },
    risk_score:   { type: Number, default: 0, min: 0, max: 1 },
    reasoning:    { type: String, default: "", maxlength: 2000 },
    action_plan:  { type: String, default: "", maxlength: 1000 },
    execution_ms: { type: Number, default: 0, min: 0 },
    request_id:   { type: String, default: "", maxlength: 100 },
  },
  {
    timestamps: { createdAt: "created_at", updatedAt: false },
    collection: "finance_decisions",
  }
);

financeDecisionSchema.index({ entity: 1, entity_id: 1 });
financeDecisionSchema.index({ decision: 1 });
financeDecisionSchema.index({ created_at: -1 });

export const FinanceDecision = mongoose.model("FinanceDecision", financeDecisionSchema);


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE AUDIT
// ══════════════════════════════════════════════════════════════════════════════

const financeAuditSchema = new mongoose.Schema(
  {
    domain:     { type: String, required: true, maxlength: 50, index: true },
    entity_id:  { type: mongoose.Schema.Types.ObjectId, required: true, index: true },
    customer_id:{ type: mongoose.Schema.Types.ObjectId, default: null, index: true },
    decision:   { type: String, default: "", maxlength: 100 },
    risk_score: { type: Number, default: 0, min: 0, max: 1 },
    confidence: { type: Number, default: 0, min: 0, max: 1 },
    decision_source: { type: String, default: "agent", maxlength: 100 },
    override_rule:   { type: String, default: "", maxlength: 100 },
    llm_used:        { type: Boolean, default: false },
    execution_ms:    { type: Number, default: 0, min: 0 },
    request_id:      { type: String, default: "", maxlength: 100 },
    action_plan:     { type: [String], default: [] },
    flags:           { type: [String], default: [] },
  },
  {
    timestamps: { createdAt: "created_at", updatedAt: false },
    collection: "finance_audit",
  }
);

financeAuditSchema.index({ created_at: -1 });
financeAuditSchema.index({ decision: 1 });

export const FinanceAudit = mongoose.model("FinanceAudit", financeAuditSchema);


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE COLLECTION LOG
// ══════════════════════════════════════════════════════════════════════════════

const financeCollectionLogSchema = new mongoose.Schema(
  {
    invoice_id:  { type: mongoose.Schema.Types.ObjectId, ref: "FinanceInvoice", index: true },
    customer_id: { type: mongoose.Schema.Types.ObjectId, ref: "Customer", index: true },
    action_type: {
      type: String,
      default: "email",
      enum: ACTION_TYPES,
      maxlength: 100,
      index: true,
    },
    template_name: { type: String, default: "", maxlength: 100 },
    subject:       { type: String, default: "", maxlength: 300 },
    body:          { type: String, default: "", maxlength: 5000 },
    priority: {
      type: String,
      default: "medium",
      enum: PRIORITIES,
    },
    status: {
      type: String,
      default: "sent",
      enum: LOG_STATUSES,
    },
    sent_at: { type: Date, default: Date.now, index: true },
  },
  {
    timestamps: false,
    collection: "finance_collection_log",
  }
);

financeCollectionLogSchema.index({ sent_at: -1 });

export const FinanceCollectionLog = mongoose.model(
  "FinanceCollectionLog",
  financeCollectionLogSchema
);


// ══════════════════════════════════════════════════════════════════════════════
//  LEGAL CASE
// ══════════════════════════════════════════════════════════════════════════════

const legalTimelineEntrySchema = new mongoose.Schema(
  {
    event: { type: String, required: true },
    date:  { type: Date, required: true, default: Date.now },
    note:  { type: String, default: "", maxlength: 500 },
  },
  { _id: false }
);

const legalCaseSchema = new mongoose.Schema(
  {
    invoice_id:  {
      type: mongoose.Schema.Types.ObjectId,
      ref: "FinanceInvoice",
      required: true,
      index: true,
    },
    customer_id: { type: mongoose.Schema.Types.ObjectId, ref: "Customer", index: true },
    case_ref: {
      type: String,
      required: true,
      unique: true,
      index: true,
    }, // e.g. LEG-202506-A3F1B2
    case_type:   { type: String, default: "debt_collection", maxlength: 100 },
    amount:      { type: Number, default: 0, min: 0 },
    status: {
      type: String,
      default: "opened",
      enum: CASE_STATUSES,
      index: true,
    },
    priority: {
      type: String,
      default: "high",
      enum: PRIORITIES,
    },
    assigned_to:  { type: String, default: "legal_team" },
    description:  { type: String, default: "", maxlength: 2000 },
    timeline:     { type: [legalTimelineEntrySchema], default: [] },
    sla_deadline: { type: Date, required: true },
    resolution:   { type: String, default: "", maxlength: 2000 },
    resolved_at:  { type: Date, default: null },
  },
  {
    timestamps: { createdAt: "created_at", updatedAt: "updated_at" },
    collection: "legal_cases",
  }
);

export const LegalCase = mongoose.model("LegalCase", legalCaseSchema);