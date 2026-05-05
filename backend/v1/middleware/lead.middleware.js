// middleware/lead.middleware.js

import { validationResult } from "express-validator";

export const handleValidation = (req, res, next) => {
  const errors = validationResult(req);

  if (!errors.isEmpty()) {
    return res.status(400).json({
      status: "failed",
      data: errors.array(),
      message: "Validation error"
    });
  }

  next();
};