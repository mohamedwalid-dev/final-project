// middleware/lead.middleware.js

import { validationResult } from "express-validator";

export const sanitizeLeadProductInput = (req, res, next) => {
  if (typeof req.body?.productName === "string") {
    req.body.productName = req.body.productName.trim();
  }

  if (typeof req.body?.category === "string") {
    req.body.category = req.body.category.trim();
  }

  if (typeof req.body?.sku === "string") {
    req.body.sku = req.body.sku.trim().toUpperCase();
  }

  if (req.body?.price !== undefined) {
    req.body.price = Number(req.body.price);
  }

  next();
};

export const handleValidation = (req, res, next) => {
  const errors = validationResult(req);

  if (!errors.isEmpty()) {
    return res.status(400).json({
      status: "failed",
      data: errors.array(),
      message: "Validation error",
    });
  }

  next();
};