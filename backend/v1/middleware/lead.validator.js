// middleware/lead.validator.js

import { body } from "express-validator";

export const validateLead = [
  body("companyName")
    .notEmpty()
    .withMessage("companyName is required")
    .isString()
    .withMessage("companyName must be a string")
    .trim(),

  body("dealValue")
    .notEmpty()
    .withMessage("dealValue is required")
    .isNumeric()
    .withMessage("dealValue must be a number")
    .custom(value => value >= 0)
    .withMessage("dealValue must be >= 0"),

  body("priority")
    .notEmpty()
    .withMessage("priority is required")
    .isIn(["Low", "Medium", "High"])
    .withMessage("priority must be Low, Medium, or High"),

  body("stage")
    .notEmpty()
    .withMessage("stage is required")
    .isIn(["New", "Contacted", "Qualified", "Proposal", "Closed Won", "Closed Lost"])
    .withMessage("invalid stage value")
];