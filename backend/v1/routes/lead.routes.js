// routes/lead.routes.js

import express from "express";
import {
  createLead,
  getAllLeads,
  getLeadById,
  updateLead,
  deleteLead
} from "../controllers/lead.controller.js";

import { validateLead } from "../middleware/lead.validator.js";
import { handleValidation } from "../middleware/lead.middleware.js";

const router = express.Router();

router.post("/", validateLead, handleValidation, createLead);
router.get("/", getAllLeads);
router.get("/:id", getLeadById);
router.put("/:id", validateLead, handleValidation, updateLead);
router.patch("/:id", validateLead, handleValidation, updateLead);
router.delete("/:id", deleteLead);

export default router;
