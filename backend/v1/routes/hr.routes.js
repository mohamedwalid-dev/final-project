/**
 * routes/hr.routes.js — HR Domain Routes
 * ========================================
 * ✅ AI Integration (added):
 *   GET /leaves/:id/decision          → polls Python for leave AI decision
 *   GET /salary-reviews/:id/decision  → polls Python for salary AI decision
 *   GET /absence-events/:id/decision  → polls Python for absence AI decision
 *   GET /incentive-requests/:id/decision → polls Python for incentive AI decision
 */

import express from "express";
import * as hrController from "../controllers/hr.controller.js";
import { Verify, VerifyRole } from "../middleware/verify.js";
import {
  validateCreateLeave,
  validateCreateSalaryReview,
  validateCreateAbsenceEvent,
  validateCreateIncentiveRequest,
  validateCreateBalanceAudit,
  validationHandler,
} from "../middleware/hr.middleware.js";

const router = express.Router();

const validate = (rules) => [...rules, validationHandler];

// ── HR Dashboard ───────────────────────────────────────────────────────────
router.get("/dashboard", Verify, hrController.getHRDashboardStats);

// ══════════════════════════════════════════════════════════════════════════════
//  LEAVE ROUTES
// ══════════════════════════════════════════════════════════════════════════════

// ⚠️  /pending and /employee/:id MUST come before /:id — Express matches top-down
router.post(  "/leaves",                      Verify, validate(validateCreateLeave), hrController.createLeave);
router.get(   "/leaves",                      Verify, hrController.getAllLeaves);
router.get(   "/leaves/pending",              Verify, hrController.getPendingLeaves);
router.get(   "/leaves/employee/:employee_id",Verify, hrController.getEmployeeLeaves);
router.get(   "/leaves/:id",                  Verify, hrController.getLeaveById);
router.get(   "/leaves/:id/decision",         Verify, hrController.getLeaveDecisionById);   // ✅ AI
router.patch( "/leaves/:id/status",           Verify, hrController.updateLeaveStatus);
router.delete("/leaves/:id",                  Verify, hrController.deleteLeave);

// ══════════════════════════════════════════════════════════════════════════════
//  SALARY REVIEW ROUTES
// ══════════════════════════════════════════════════════════════════════════════

router.post(  "/salary-reviews",              Verify, validate(validateCreateSalaryReview), hrController.createSalaryReview);
router.get(   "/salary-reviews",              Verify, hrController.getAllSalaryReviews);
router.get(   "/salary-reviews/pending",      Verify, hrController.getPendingSalaryReviews);
router.get(   "/salary-reviews/:id",          Verify, hrController.getSalaryReviewById);
router.get(   "/salary-reviews/:id/decision", Verify, hrController.getSalaryReviewDecisionById); // ✅ AI
router.patch( "/salary-reviews/:id/status",   Verify, hrController.updateSalaryReviewStatus);
router.delete("/salary-reviews/:id",          Verify, hrController.deleteSalaryReview);

// ══════════════════════════════════════════════════════════════════════════════
//  ABSENCE EVENT ROUTES
// ══════════════════════════════════════════════════════════════════════════════

router.post(  "/absence-events",                       Verify, validate(validateCreateAbsenceEvent), hrController.createAbsenceEvent);
router.get(   "/absence-events",                       Verify, hrController.getAllAbsenceEvents);
router.get(   "/absence-events/pending",               Verify, hrController.getPendingAbsenceEvents);
router.get(   "/absence-events/employee/:employee_id", Verify, hrController.getEmployeeAbsences);
router.get(   "/absence-events/:id",                   Verify, hrController.getAbsenceEventById);
router.get(   "/absence-events/:id/decision",          Verify, hrController.getAbsenceDecisionById);  // ✅ AI
router.patch( "/absence-events/:id/status",            Verify, hrController.updateAbsenceEventStatus);
router.delete("/absence-events/:id",                   Verify, hrController.deleteAbsenceEvent);

// ══════════════════════════════════════════════════════════════════════════════
//  INCENTIVE REQUEST ROUTES
// ══════════════════════════════════════════════════════════════════════════════

router.post(  "/incentive-requests",              Verify, validate(validateCreateIncentiveRequest), hrController.createIncentiveRequest);
router.get(   "/incentive-requests",              Verify, hrController.getAllIncentiveRequests);
router.get(   "/incentive-requests/pending",      Verify, hrController.getPendingIncentiveRequests);
router.get(   "/incentive-requests/:id",          Verify, hrController.getIncentiveRequestById);
router.get(   "/incentive-requests/:id/decision", Verify, hrController.getIncentiveDecisionById);     // ✅ AI
router.patch( "/incentive-requests/:id/status",   Verify, hrController.updateIncentiveStatus);
router.delete("/incentive-requests/:id",          Verify, hrController.deleteIncentiveRequest);

// ══════════════════════════════════════════════════════════════════════════════
//  HR AUDIT ROUTES
// ══════════════════════════════════════════════════════════════════════════════

router.post("/audit",                    Verify, hrController.createHRAuditEntry);
router.get( "/audit/:domain/:entity_id", Verify, hrController.getHRAuditByEntity);

// ── Balance Audit ──────────────────────────────────────────────────────────
router.post("/balance-audit",              Verify, validate(validateCreateBalanceAudit), hrController.createBalanceAuditEntry);
router.get( "/balance-audit/:employee_id", Verify, hrController.getBalanceHistory);

export default router;