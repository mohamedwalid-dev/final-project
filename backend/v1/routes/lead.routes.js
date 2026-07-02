  // routes/lead.routes.js

import express from "express";
import {
  addProductToLead,
  createLead,
  deleteLead,
  deleteProductFromLead,
  getAllLeads,
  getInventorySuggestions,
  getLeadById,
  updateLead,
  updateProductInLead,
} from "../controllers/lead.controller.js";

import { validateLead, validateLeadProduct } from "../middleware/lead.validator.js";
import { handleValidation, sanitizeLeadProductInput } from "../middleware/lead.middleware.js";

const router = express.Router();

router.get("/products/suggestions", getInventorySuggestions);
router.post("/", validateLead, handleValidation, createLead);
router.post("/:id/products", sanitizeLeadProductInput, validateLeadProduct, handleValidation, addProductToLead);
router.put("/:leadId/products/:productId", sanitizeLeadProductInput, validateLeadProduct, handleValidation, updateProductInLead);
router.delete("/:leadId/products/:productId", deleteProductFromLead);
router.get("/", getAllLeads);

router
  .route("/:id")
  .get(getLeadById)
  .put(validateLead, handleValidation, updateLead)
  .patch(validateLead, handleValidation, updateLead)
  .delete(deleteLead);

export default router;
