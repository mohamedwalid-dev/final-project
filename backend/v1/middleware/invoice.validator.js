// middleware/invoice.validator.js

import { body } from "express-validator";

export const validateInvoice = [

  body("status")
    .optional()
    .isIn(["Paid", "Pending", "Overdue"])
    .withMessage("status must be Paid, Pending, or Overdue"),
    
  body("clientInformation.customerName")
    .notEmpty()
    .withMessage("Customer name is required")
    .isString(),

  body("clientInformation.billingEmail")
    .notEmpty()
    .withMessage("Billing email is required")
    .isEmail()
    .withMessage("Invalid email format"),

  body("clientInformation.billingAddress")
    .notEmpty()
    .withMessage("Billing address is required")
    .isString(),

  body("invoiceTimeline.issueDate")
    .notEmpty()
    .withMessage("Issue date is required")
    .isISO8601(),

  body("invoiceTimeline.dueDate")
    .notEmpty()
    .withMessage("Due date is required")
    .isISO8601(),

  body("invoiceTimeline.currency")
    .notEmpty()
    .withMessage("Currency is required")
    .isString(),

  body("lineItems")
    .isArray({ min: 1 })
    .withMessage("At least one line item is required"),

  body("lineItems.*.description")
    .notEmpty()
    .withMessage("Line item description is required"),

  body("lineItems.*.quantity")
    .notEmpty()
    .withMessage("Quantity is required")
    .isInt({ min: 1 }),

  body("lineItems.*.unitPrice")
    .notEmpty()
    .withMessage("Unit price is required")
    .isFloat({ min: 0 }),

  body("lineItems.*.total")
    .notEmpty()
    .withMessage("Total is required")
    .isFloat({ min: 0 }),

  body("taxConfiguration.customTaxRate")
    .optional()
    .isFloat({ min: 0, max: 100 })
    .withMessage("Tax rate must be between 0 and 100"),

  body("discountAndNotes.discountAmountUSD")
    .optional()
    .isFloat({ min: 0 }),
];