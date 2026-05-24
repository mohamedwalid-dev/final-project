// middleware/newProduct.middleware.js

import { validationResult } from "express-validator";

export const validateRequest = (req, res, next) => {
  const errors = validationResult(req);

  if (!errors.isEmpty()) {
    const firstError = errors.array()[0];

    return res.status(400).json({
      status: "failed",
      data: errors.array(),
      message: firstError?.msg || "Validation error",
    });
  }

  next();
};
