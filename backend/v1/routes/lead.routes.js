// routes/lead.routes.js

import express from "express";
import {
  createLead,
  getAllLeads,
  getLeadById,
  updateLead,
  deleteLead,
} from "../controllers/lead.controller.js";

import { validateLead } from "../middleware/lead.validator.js";
import { handleValidation } from "../middleware/lead.middleware.js";

const router = express.Router();

router.post("/", validateLead, handleValidation, createLead);
router.get("/", getAllLeads);

router
  .route("/:id")
  .get(getLeadById)
  .put(validateLead, handleValidation, updateLead)
  .patch(validateLead, handleValidation, updateLead)
  .delete(deleteLead);

export default router;
