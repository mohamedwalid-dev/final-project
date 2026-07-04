import express from "express";
import * as financeController from "../controllers/finance.controller.js";
import { Verify, VerifyRole } from "../middleware/verify.js";

const router = express.Router();

// Finance Dashboard
router.get("/dashboard", Verify, financeController.getFinanceDashboardStats);
router.get("/forecast", Verify, financeController.getCashflowForecast);

// Finance Invoice Routes
router.post("/invoices", Verify, financeController.createInvoice);
router.get("/invoices", Verify, financeController.getAllInvoices);
router.get("/invoices/pending", Verify, financeController.getPendingInvoices);
router.get("/invoices/overdue", Verify, financeController.getOverdueInvoices);
router.get("/invoices/:id", Verify, financeController.getInvoiceById);
router.patch("/invoices/:id/status", Verify, financeController.updateInvoiceStatus);
router.patch("/invoices/:id/strategy", Verify, financeController.updateInvoiceCollectionStrategy);
router.delete("/invoices/:id", Verify, financeController.deleteInvoice);

// Customer Routes
router.post("/customers", Verify, financeController.createCustomer);
router.get("/customers", Verify, financeController.getAllCustomers);
router.get("/customers/:id", Verify, financeController.getCustomerById);
router.patch("/customers/:id", Verify, financeController.updateCustomer);
router.delete("/customers/:id", Verify, financeController.deleteCustomer);

// Escalation and Legal Actions
router.get("/escalations/active", Verify, financeController.getActiveEscalations);
router.get("/escalations/:invoice_id", Verify, financeController.getEscalationStatus);

router.post("/legal-cases", Verify, financeController.createLegalCase);
router.get("/legal-cases", Verify, financeController.getLegalCases);
router.get("/legal-cases/:id", Verify, financeController.getLegalCaseById);
router.patch("/legal-cases/:id/status", Verify, financeController.updateLegalCaseStatus);

// Collections
router.post("/collections/log", Verify, financeController.logCollectionAction);
router.get("/collections/log", Verify, financeController.getCollectionLog);
router.get("/collections/stats", Verify, financeController.getCollectionActionStats);

// Finance Audit and Decisions
router.post("/audit", Verify, financeController.writeFinanceAudit);
router.get("/audit/:domain/:entity_id", Verify, financeController.getFinanceAudit);

router.post("/decisions", Verify, financeController.saveFinanceDecision);
router.get("/decisions/history", Verify, financeController.getDecisionsHistory);   // ✅ جديد — لازم يجي قبل /:entity_id
router.get("/decisions/:entity_id", Verify, financeController.getFinanceDecisions);

export default router;
