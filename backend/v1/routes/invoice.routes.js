// routes/invoice.routes.js

import express from "express";
import {
  createInvoice,
  getAllInvoices,
  getInvoiceById,
  updateInvoice,
  deleteInvoice,
} from "../controllers/invoice.controller.js";

import { validateInvoice } from "../middleware/invoice.validator.js";
import { validationHandler } from "../middleware/invoice.middleware.js";

const router = express.Router();

router.post("/", validateInvoice, validationHandler, createInvoice);

router.get("/", getAllInvoices);
router.get("/:id", getInvoiceById);

router.put("/:id", validateInvoice, validationHandler, updateInvoice);

// PATCH is for partial updates, so don't use the full create invoice validator here
router.patch("/:id", updateInvoice);

router.delete("/:id", deleteInvoice);

export default router;