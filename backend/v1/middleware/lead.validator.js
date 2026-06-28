// middleware/lead.validator.js

import { body } from "express-validator";

const allowedPriority = ["Low", "Medium", "High"];
const allowedStage = ["New", "Contacted", "Proposal", "Negotiation", "Closed", "Closed Won", "Closed Lost"];
const allowedStatus = ["Open", "Won", "Lost"];

export const validateLead = [
  body("clientName")
    .optional({ values: "falsy" })
    .trim()
    .isString()
    .withMessage("clientName must be a string")
    .isLength({ min: 2, max: 100 })
    .withMessage("clientName must be between 2 and 100 characters"),

  body("companyName")
    .optional({ values: "falsy" })
    .trim()
    .isString()
    .withMessage("companyName must be a string")
    .isLength({ min: 2, max: 100 })
    .withMessage("companyName must be between 2 and 100 characters"),

  body("email")
    .optional({ values: "falsy" })
    .trim()
    .isEmail()
    .withMessage("email must be a valid email address"),

  body("phone")
    .optional({ values: "falsy" })
    .trim()
    .isString()
    .withMessage("phone must be a string")
    .isLength({ min: 7, max: 20 })
    .withMessage("phone must be between 7 and 20 characters"),

  body("address")
    .optional({ values: "falsy" })
    .trim()
    .isString()
    .withMessage("address must be a string"),

  body("dealValue")
    .optional({ values: "falsy" })
    .isNumeric()
    .withMessage("dealValue must be a number")
    .custom((value) => Number(value) >= 0)
    .withMessage("dealValue must be >= 0"),

  body("priority")
    .optional({ values: "falsy" })
    .trim()
    .isIn(allowedPriority)
    .withMessage("priority must be Low, Medium, or High"),

  body("stage")
    .optional({ values: "falsy" })
    .trim()
    .isIn(allowedStage)
    .withMessage("invalid stage value"),

  body("status")
    .optional({ values: "falsy" })
    .trim()
    .isIn(allowedStatus)
    .withMessage("status must be Open, Won, or Lost"),

  body().custom((_, { req }) => {
    const hasClientName = Boolean(req.body.clientName?.trim());
    const hasCompanyName = Boolean(req.body.companyName?.trim());

    if (!hasClientName && !hasCompanyName) {
      throw new Error("clientName or companyName is required");
    }

    return true;
  }),
];