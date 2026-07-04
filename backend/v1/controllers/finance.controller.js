/**
 * controllers/finance.controller.js — Finance Domain Controllers
 * ================================================================
 * Covers: Customer / FinanceInvoice / FinanceDecision / FinanceAudit /
 *         FinanceCollectionLog / LegalCase + Dashboard + Cashflow
 *
 * ✅ AI Integration (added):
 *   - runRiskPrediction   → calls Python /finance/predict-risk (ML model)
 *   - getAIDashboardData  → calls Python /finance/actions/dashboard-data (cached)
 */

import mongoose from "mongoose";
import { v4 as uuidv4 } from "uuid";
import {
  Customer,
  FinanceInvoice,
  FinanceDecision,
  FinanceAudit,
  FinanceCollectionLog,
  LegalCase,
} from "../models/finance.model.js";

import {
  predictInvoiceRisk,
  getAIFinanceDashboard,
} from "../services/aiService.js";

// ── Shared helpers ─────────────────────────────────────────────────────────

const sendSuccess = (res, data, message = "Success", statusCode = 200) =>
  res.status(statusCode).json({ status: "success", data, message });

const sendError = (res, message = "Internal Server Error", statusCode = 500, data = []) =>
  res.status(statusCode).json({ status: "failed", data, message });

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

const invoiceWithCustomerPipeline = (matchStage) => [
  { $match: matchStage },
  {
    $lookup: {
      from:         "customers",
      localField:   "customer_id",
      foreignField: "_id",
      as:           "_customer",
    },
  },
  { $unwind: { path: "$_customer", preserveNullAndEmptyArrays: true } },
  {
    $addFields: {
      customer_name:  "$_customer.name",
      customer_email: "$_customer.email",
      customer_phone: "$_customer.phone",
      credit_score:   "$_customer.credit_score",
      industry:       "$_customer.industry",
      service_status: "$_customer.service_status",
      is_blacklisted: "$_customer.is_blacklisted",
      overdue_days_calc: {
        $toInt: {
          $divide: [
            { $subtract: [new Date(), "$due_date"] },
            86_400_000,
          ],
        },
      },
    },
  },
  { $project: { _customer: 0 } },
];


// ══════════════════════════════════════════════════════════════════════════════
//  AI — RISK PREDICTION & DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════

/**
 * POST /v1/finance/ai/predict-risk
 * Calls Python ML model (XGBoost + LightGBM ensemble).
 * Returns: { decision, risk_score, confidence, reasons, positive_factors, ... }
 *
 * Can optionally auto-update invoice risk_score in MongoDB if invoice_id provided.
 */
export const runRiskPrediction = async (req, res) => {
  try {
    const riskInput = {
      overdue_days_normalized:   Number(req.body.overdue_days_normalized   ?? 0),
      amount_normalized:         Number(req.body.amount_normalized         ?? 0),
      paid_ratio:                Number(req.body.paid_ratio                ?? 1),
      late_ratio:                Number(req.body.late_ratio                ?? 0),
      on_time_ratio:             Number(req.body.on_time_ratio             ?? 1),
      customer_age_normalized:   Number(req.body.customer_age_normalized   ?? 0.5),
      invoice_frequency:         Number(req.body.invoice_frequency         ?? 0.5),
      avg_delay_normalized:      Number(req.body.avg_delay_normalized      ?? 0),
      credit_score_normalized:   Number(req.body.credit_score_normalized   ?? 0.8),
      industry_risk_factor:      Number(req.body.industry_risk_factor      ?? 0.35),
      seasonal_factor:           Number(req.body.seasonal_factor           ?? 0.35),
      industry:                  req.body.industry      ?? undefined,
      invoice_month:             req.body.invoice_month ?? undefined,
    };

    const result = await predictInvoiceRisk(riskInput);

    // Optional: auto-update invoice if invoice_id provided in the request body
    if (req.body.invoice_id) {
      const oid = toOid(req.body.invoice_id);
      if (oid) {
        await FinanceInvoice.findByIdAndUpdate(oid, {
          $set: {
            ai_risk_score:      result.risk_score,
            ai_decision:        result.decision?.substring(0, 100),
            ai_decision_reason: (result.reasons?.[0] || "").substring(0, 1000),
            ai_request_id:      (result.request_id  || "").substring(0, 100),
          },
        });
      }
    }

    return sendSuccess(res, result, "Risk prediction complete");
  } catch (err) {
    if (err.code === "AI_AGENT_DOWN")        return sendError(res, err.message, 503);
    if (err.code === "AI_MODEL_NOT_LOADED")  return sendError(res, err.message, 503);
    return sendError(res, err.message);
  }
};

/**
 * GET /v1/finance/ai/dashboard?days=7
 * Returns AI agent dashboard data (action stats, escalations, legal cases).
 * Python side has L1/L2/L3 layered cache — usually < 5ms.
 */
export const getAIDashboardData = async (req, res) => {
  try {
    const days   = Number(req.query.days) || 7;
    const result = await getAIFinanceDashboard(days);
    return sendSuccess(res, result, "AI finance dashboard data fetched");
  } catch (err) {
    if (err.code === "AI_AGENT_DOWN") return sendError(res, err.message, 503);
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  CUSTOMER
// ══════════════════════════════════════════════════════════════════════════════

export const createCustomer = async (req, res) => {
  try {
    const customer = await Customer.create(req.body);
    return sendSuccess(res, customer, "Customer created", 201);
  } catch (err) {
    if (err.code === 11000)
      return sendError(res, "Customer with this email already exists", 409);
    return sendError(res, err.message);
  }
};

export const getAllCustomers = async (req, res) => {
  try {
    const { service_status, is_blacklisted, limit = 50, skip = 0 } = req.query;
    const filter = {};
    if (service_status) filter.service_status = service_status;
    if (is_blacklisted !== undefined)
      filter.is_blacklisted = is_blacklisted === "true";

    const [customers, total] = await Promise.all([
      Customer.find(filter).sort({ created_at: -1 }).skip(Number(skip)).limit(Number(limit)),
      Customer.countDocuments(filter),
    ]);

    return sendSuccess(res, { customers, total }, "Customers fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getCustomerById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const customer = await Customer.findById(oid);
    if (!customer) return sendError(res, "Customer not found", 404);

    const summary = await FinanceInvoice.aggregate([
      { $match: { customer_id: oid } },
      {
        $group: {
          _id:                null,
          total:              { $sum: 1 },
          paid:               { $sum: { $cond: [{ $eq: ["$status", "paid"] },         1, 0] } },
          overdue:            { $sum: { $cond: [{ $eq: ["$status", "overdue"] },       1, 0] } },
          legal:              { $sum: { $cond: [{ $eq: ["$status", "legal"] },         1, 0] } },
          written_off:        { $sum: { $cond: [{ $eq: ["$status", "written_off"] },   1, 0] } },
          total_amount:       { $sum: "$amount" },
          paid_amount:        { $sum: { $cond: [{ $eq: ["$status", "paid"] }, "$amount", 0] } },
          outstanding_amount: {
            $sum: {
              $cond: [{ $in: ["$status", ["overdue", "legal"]] }, "$amount", 0],
            },
          },
        },
      },
    ]);

    return sendSuccess(
      res,
      { ...customer.toObject(), invoice_summary: summary[0] ?? {} },
      "Customer fetched"
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const updateCustomer = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const updates = { ...req.body };
    if (updates.is_blacklisted === true  && !updates.blacklisted_at) updates.blacklisted_at = new Date();
    if (updates.service_status === "suspended" && !updates.suspended_at) updates.suspended_at = new Date();

    const updated = await Customer.findByIdAndUpdate(
      oid,
      { $set: updates },
      { new: true, runValidators: true }
    );
    if (!updated) return sendError(res, "Customer not found", 404);

    return sendSuccess(res, updated, "Customer updated");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const deleteCustomer = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const deleted = await Customer.findByIdAndDelete(oid);
    if (!deleted) return sendError(res, "Customer not found", 404);

    return sendSuccess(res, [], "Customer deleted");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE INVOICE
// ══════════════════════════════════════════════════════════════════════════════

export const createInvoice = async (req, res) => {
  try {
    const oid = resolveOid(res, req.body.customer_id);
    if (!oid) return;

    const customerExists = await Customer.exists({ _id: oid });
    if (!customerExists) return sendError(res, "Customer not found", 404);

    const invoice = await FinanceInvoice.create({ ...req.body, customer_id: oid });
    return sendSuccess(res, invoice, "Finance invoice created", 201);
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getAllInvoices = async (req, res) => {
  try {
    const { status, customer_id, limit = 100, skip = 0 } = req.query;
    const filter = {};
    if (status)      filter.status      = status;
    if (customer_id) {
      const oid = toOid(customer_id);
      if (oid) filter.customer_id = oid;
    }

    const [invoices, total] = await Promise.all([
      FinanceInvoice.find(filter)
        .sort({ due_date: 1, amount: -1 })
        .skip(Number(skip))
        .limit(Number(limit)),
      FinanceInvoice.countDocuments(filter),
    ]);

    return sendSuccess(res, { invoices, total }, "Finance invoices fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getInvoiceById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const docs = await FinanceInvoice.aggregate(invoiceWithCustomerPipeline({ _id: oid }));
    if (!docs.length) return sendError(res, "Finance invoice not found", 404);

    return sendSuccess(res, docs[0], "Finance invoice fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getPendingInvoices = async (req, res) => {
  try {
    const invoices = await FinanceInvoice.find({
      status:   { $nin: ["paid", "written_off", "cancelled"] },
      due_date: { $lte: new Date() },
    }).sort({ due_date: 1, amount: -1 });

    return sendSuccess(res, invoices, "Pending finance invoices fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getOverdueInvoices = async (req, res) => {
  try {
    const minDays = Number(req.query.min_days) || 1;
    const limit   = Number(req.query.limit)    || 200;
    const cutoff  = new Date(Date.now() - minDays * 86_400_000);

    const invoices = await FinanceInvoice.find({
      status:   { $nin: ["paid", "written_off", "cancelled"] },
      due_date: { $lt: cutoff },
    })
      .sort({ due_date: 1 })
      .limit(limit);

    return sendSuccess(res, invoices, "Overdue finance invoices fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const updateInvoiceStatus = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const {
      status, ai_decision = "", risk_score = 0,
      decision_reason = "", action_plan = "", request_id = "",
    } = req.body;

    const updated = await FinanceInvoice.findByIdAndUpdate(
      oid,
      {
        $set: {
          status,
          ai_decision:        ai_decision.substring(0, 100),
          ai_risk_score:      Number(risk_score),
          ai_decision_reason: decision_reason.substring(0, 1000),
          ai_action_plan:     action_plan.substring(0, 500),
          ai_request_id:      request_id.substring(0, 100),
        },
      },
      { new: true, runValidators: true }
    );

    if (!updated) return sendError(res, "Finance invoice not found", 404);
    return sendSuccess(res, updated, "Finance invoice status updated");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const updateInvoiceCollectionStrategy = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const {
      risk_score = 0, collection_strategy = "standard",
      first_reminder_days = 7, request_id = "",
    } = req.body;

    const updated = await FinanceInvoice.findByIdAndUpdate(
      oid,
      {
        $set: {
          ai_risk_score:       Number(risk_score),
          collection_strategy: String(collection_strategy).substring(0, 50),
          first_reminder_days: Number(first_reminder_days),
          ai_request_id:       request_id.substring(0, 100),
        },
      },
      { new: true, runValidators: true }
    );

    if (!updated) return sendError(res, "Finance invoice not found", 404);
    return sendSuccess(res, updated, "Collection strategy updated");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const deleteInvoice = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const deleted = await FinanceInvoice.findByIdAndDelete(oid);
    if (!deleted) return sendError(res, "Finance invoice not found", 404);

    return sendSuccess(res, [], "Finance invoice deleted");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE DECISIONS
// ══════════════════════════════════════════════════════════════════════════════

export const saveFinanceDecision = async (req, res) => {
  try {
    const oid = resolveOid(res, req.body.entity_id);
    if (!oid) return;

    const decision = await FinanceDecision.create({ ...req.body, entity_id: oid });
    return sendSuccess(res, decision, "Finance decision saved", 201);
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getFinanceDecisions = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.entity_id);
    if (!oid) return;

    const entity = req.query.entity || "finance_invoices";
    const decisions = await FinanceDecision.find({ entity, entity_id: oid })
      .sort({ created_at: -1 });

    return sendSuccess(res, decisions, "Finance decisions fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getDecisionsHistory = async (req, res) => {
  try {
    const { entity = "finance_invoices", limit = 100, decision } = req.query;
    const filter = { entity };
    if (decision) filter.decision = decision;

    const decisions = await FinanceDecision.find(filter)
      .sort({ created_at: -1 })
      .limit(Number(limit));

    return sendSuccess(res, decisions, "Decisions history fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE AUDIT
// ══════════════════════════════════════════════════════════════════════════════

export const writeFinanceAudit = async (req, res) => {
  try {
    const oid = resolveOid(res, req.body.entity_id);
    if (!oid) return;

    const entry = await FinanceAudit.create({
      ...req.body,
      entity_id:   oid,
      customer_id: req.body.customer_id ? toOid(req.body.customer_id) : null,
      risk_score:  parseFloat(req.body.risk_score || 0).toFixed(4),
      confidence:  parseFloat(req.body.confidence || 0).toFixed(4),
    });

    return sendSuccess(res, entry, "Finance audit entry written", 201);
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getFinanceAudit = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.entity_id);
    if (!oid) return;

    const { domain } = req.params;
    const entries = await FinanceAudit.find({ domain, entity_id: oid })
      .sort({ created_at: -1 });

    return sendSuccess(res, entries, "Finance audit entries fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  COLLECTION LOG
// ══════════════════════════════════════════════════════════════════════════════

export const logCollectionAction = async (req, res) => {
  try {
    const entry = await FinanceCollectionLog.create(req.body);
    return sendSuccess(res, entry, "Collection action logged", 201);
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getCollectionLog = async (req, res) => {
  try {
    const { invoice_id, customer_id, action_type, limit = 50 } = req.query;
    const filter = {};
    if (invoice_id)  filter.invoice_id  = toOid(invoice_id)  || invoice_id;
    if (customer_id) filter.customer_id = toOid(customer_id) || customer_id;
    if (action_type) filter.action_type = action_type;

    const logs = await FinanceCollectionLog.find(filter)
      .sort({ sent_at: -1 })
      .limit(Number(limit));

    return sendSuccess(res, logs, "Collection log fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getCollectionActionStats = async (req, res) => {
  try {
    const days  = Number(req.query.days) || 7;
    const since = new Date(Date.now() - days * 86_400_000);

    const [breakdown, summaryDocs] = await Promise.all([
      FinanceCollectionLog.aggregate([
        { $match: { sent_at: { $gte: since } } },
        {
          $group: {
            _id:   { action_type: "$action_type", status: "$status", priority: "$priority" },
            count: { $sum: 1 },
          },
        },
        { $sort: { count: -1 } },
        {
          $project: {
            _id:         0,
            action_type: "$_id.action_type",
            status:      "$_id.status",
            priority:    "$_id.priority",
            count:       1,
          },
        },
      ]),
      FinanceCollectionLog.aggregate([
        { $match: { sent_at: { $gte: since } } },
        {
          $group: {
            _id:               null,
            emails_sent:       { $sum: { $cond: [{ $eq: ["$action_type", "email"] },                 1, 0] } },
            legal_escalations: { $sum: { $cond: [{ $eq: ["$action_type", "legal_escalation"] },      1, 0] } },
            notifications:     { $sum: { $cond: [{ $eq: ["$action_type", "internal_notification"] }, 1, 0] } },
            system_actions:    { $sum: { $cond: [{ $eq: ["$action_type", "system"] },                1, 0] } },
            calls_scheduled:   { $sum: { $cond: [{ $eq: ["$action_type", "call_scheduled"] },        1, 0] } },
            followups:         { $sum: { $cond: [{ $eq: ["$action_type", "followup_scheduled"] },    1, 0] } },
            critical_actions:  { $sum: { $cond: [{ $eq: ["$priority",   "critical"] },               1, 0] } },
            total:             { $sum: 1 },
          },
        },
      ]),
    ]);

    return sendSuccess(
      res,
      { breakdown, summary: summaryDocs[0] ?? {} },
      `Collection stats (last ${days} days)`
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  LEGAL CASES
// ══════════════════════════════════════════════════════════════════════════════

export const createLegalCase = async (req, res) => {
  try {
    const invoiceOid = resolveOid(res, req.body.invoice_id);
    if (!invoiceOid) return;

    const invoiceExists = await FinanceInvoice.exists({ _id: invoiceOid });
    if (!invoiceExists) return sendError(res, "Finance invoice not found", 404);

    const yyyymm   = new Date().toISOString().slice(0, 7).replace("-", "");
    const case_ref = `LEG-${yyyymm}-${uuidv4().replace(/-/g, "").substring(0, 6).toUpperCase()}`;

    const sla_days     = Number(req.body.sla_days) || 7;
    const sla_deadline = new Date(Date.now() + sla_days * 86_400_000);

    const legalCase = await LegalCase.create({
      ...req.body,
      invoice_id:  invoiceOid,
      customer_id: req.body.customer_id ? toOid(req.body.customer_id) : null,
      case_ref,
      sla_deadline,
      status:      "opened",
      assigned_to: req.body.assigned_to || "legal_team",
      timeline: [
        {
          event: "case_opened",
          date:  new Date(),
          note:  `Legal case opened for finance invoice #${req.body.invoice_id}`,
        },
      ],
    });

    return sendSuccess(
      res,
      {
        case_id:    legalCase._id,
        case_ref,
        status:     "opened",
        invoice_id: req.body.invoice_id,
        sla_days,
      },
      "Legal case created",
      201
    );
  } catch (err) {
    if (err.code === 11000)
      return sendError(res, "Legal case with this reference already exists", 409);
    return sendError(res, err.message);
  }
};

export const getLegalCases = async (req, res) => {
  try {
    const { status, customer_id, limit = 50 } = req.query;
    const filter = {};
    if (status)      filter.status      = status;
    if (customer_id) filter.customer_id = toOid(customer_id) || customer_id;

    const cases = await LegalCase.find(filter)
      .sort({ created_at: -1 })
      .limit(Number(limit));

    return sendSuccess(res, cases, "Legal cases fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getLegalCaseById = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const legalCase = await LegalCase.findById(oid);
    if (!legalCase) return sendError(res, "Legal case not found", 404);

    return sendSuccess(res, legalCase, "Legal case fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const updateLegalCaseStatus = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.id);
    if (!oid) return;

    const { status, note = "", resolution = "" } = req.body;
    const terminalStatuses = ["resolved", "settled", "closed"];

    const updates = { status: String(status).substring(0, 50) };
    if (resolution)                        updates.resolution  = resolution.substring(0, 2000);
    if (terminalStatuses.includes(status)) updates.resolved_at = new Date();

    const updated = await LegalCase.findByIdAndUpdate(
      oid,
      {
        $set:  updates,
        $push: {
          timeline: {
            event: `status_changed_to_${status}`,
            date:  new Date(),
            note:  note.substring(0, 500),
          },
        },
      },
      { new: true, runValidators: true }
    );

    if (!updated) return sendError(res, "Legal case not found", 404);
    return sendSuccess(res, updated, "Legal case status updated");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  ESCALATION TRACKING
// ══════════════════════════════════════════════════════════════════════════════

const TIER_MAP    = { pending: 1, overdue: 2, suspended: 3, legal: 4, written_off: 5 };
const TIER_LABELS = { 1: "reminder", 2: "follow_up", 3: "suspension", 4: "legal", 5: "write_off" };

export const getEscalationStatus = async (req, res) => {
  try {
    const oid = resolveOid(res, req.params.invoice_id);
    if (!oid) return;

    const [invoice, actions, legalCases] = await Promise.all([
      FinanceInvoice.findById(oid),
      FinanceCollectionLog.find(
        { invoice_id: oid },
        { action_type: 1, template_name: 1, priority: 1, status: 1, sent_at: 1 }
      ).sort({ sent_at: -1 }).limit(20),
      LegalCase.find(
        { invoice_id: oid },
        { case_ref: 1, status: 1, priority: 1, created_at: 1, sla_deadline: 1 }
      ).sort({ created_at: -1 }),
    ]);

    if (!invoice) return sendError(res, "Finance invoice not found", 404);

    const current_tier = TIER_MAP[invoice.status] ?? 1;
    return sendSuccess(
      res,
      {
        invoice,
        current_tier,
        tier_label:    TIER_LABELS[current_tier] ?? "unknown",
        actions_taken: actions,
        legal_cases:   legalCases,
        action_count:  actions.length,
      },
      "Escalation status fetched"
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getActiveEscalations = async (req, res) => {
  try {
    const escalations = await FinanceInvoice.find({
      status:   { $in: ["overdue", "suspended", "legal", "payment_plan"] },
      due_date: { $lt: new Date() },
    })
      .sort({ due_date: 1 })
      .limit(100);

    return sendSuccess(res, escalations, "Active escalations fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
};


// ══════════════════════════════════════════════════════════════════════════════
//  FINANCE DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════

export const getFinanceDashboardStats = async (req, res) => {
  try {
    const thirtyAgo = new Date(Date.now() - 30 * 86_400_000);
    const sevenAgo  = new Date(Date.now() -  7 * 86_400_000);

    const [invDocs, riskDocs, decisionBreakdown, actionStats] = await Promise.all([
      FinanceInvoice.aggregate([
        {
          $group: {
            _id:               null,
            total_invoices:    { $sum: 1 },
            paid:              { $sum: { $cond: [{ $eq: ["$status", "paid"] },         1, 0] } },
            overdue:           { $sum: { $cond: [{ $eq: ["$status", "overdue"] },      1, 0] } },
            legal:             { $sum: { $cond: [{ $eq: ["$status", "legal"] },        1, 0] } },
            suspended:         { $sum: { $cond: [{ $eq: ["$status", "suspended"] },    1, 0] } },
            written_off:       { $sum: { $cond: [{ $eq: ["$status", "written_off"] },  1, 0] } },
            payment_plan:      { $sum: { $cond: [{ $eq: ["$status", "payment_plan"] }, 1, 0] } },
            disputed:          { $sum: { $cond: [{ $eq: ["$status", "disputed"] },     1, 0] } },
            total_amount:      { $sum: "$amount" },
            collected_amount:  { $sum: { $cond: [{ $eq: ["$status", "paid"] }, "$amount", 0] } },
            outstanding_amount:{
              $sum: {
                $cond: [{ $in: ["$status", ["overdue", "legal", "suspended"]] }, "$amount", 0],
              },
            },
          },
        },
      ]),
      FinanceInvoice.aggregate([
        {
          $match: {
            ai_risk_score: { $gte: 0.7 },
            status:        { $nin: ["paid", "written_off"] },
          },
        },
        {
          $group: {
            _id:              null,
            high_risk_count:  { $sum: 1 },
            high_risk_amount: { $sum: "$amount" },
          },
        },
      ]),
      FinanceDecision.aggregate([
        { $match:   { created_at: { $gte: thirtyAgo } } },
        { $group:   { _id: "$decision", count: { $sum: 1 } } },
        { $sort:    { count: -1 } },
        { $limit:   10 },
        { $project: { _id: 0, decision: "$_id", count: 1 } },
      ]),
      FinanceCollectionLog.aggregate([
        { $match:   { sent_at: { $gte: sevenAgo } } },
        { $group:   { _id: "$action_type", count: { $sum: 1 } } },
        { $project: { _id: 0, action_type: "$_id", count: 1 } },
      ]),
    ]);

    return sendSuccess(
      res,
      {
        invoices:      invDocs[0]  ?? {},
        risk:          riskDocs[0] ?? {},
        decisions_30d: decisionBreakdown,
        actions_7d:    actionStats,
        timestamp:     new Date().toISOString(),
      },
      "Finance dashboard stats fetched"
    );
  } catch (err) {
    return sendError(res, err.message);
  }
};

export const getCashflowForecast = async (req, res) => {
  try {
    const now   = new Date();
    const in7d  = new Date(now.getTime() +  7 * 86_400_000);
    const in30d = new Date(now.getTime() + 30 * 86_400_000);

    const docs = await FinanceInvoice.aggregate([
      { $match: { status: { $nin: ["paid", "written_off", "cancelled"] } } },
      {
        $group: {
          _id:                null,
          due_7_days:         {
            $sum: {
              $cond: [
                { $and: [{ $lte: ["$due_date", in7d] }, { $eq: ["$status", "pending"] }] },
                "$amount", 0,
              ],
            },
          },
          due_30_days:        {
            $sum: {
              $cond: [
                { $and: [{ $lte: ["$due_date", in30d] }, { $eq: ["$status", "pending"] }] },
                "$amount", 0,
              ],
            },
          },
          overdue_total:      { $sum: { $cond: [{ $eq: ["$status", "overdue"] }, "$amount", 0] } },
          high_risk_overdue:  {
            $sum: {
              $cond: [
                { $and: [{ $eq: ["$status", "overdue"] }, { $gte: ["$ai_risk_score", 0.7] }] },
                "$amount", 0,
              ],
            },
          },
          payment_plan_total: { $sum: { $cond: [{ $eq: ["$status", "payment_plan"] }, "$amount", 0] } },
        },
      },
    ]);

    return sendSuccess(res, docs[0] ?? {}, "Cashflow forecast fetched");
  } catch (err) {
    return sendError(res, err.message);
  }
  
};