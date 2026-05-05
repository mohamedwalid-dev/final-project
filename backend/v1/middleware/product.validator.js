// validators/newProduct.validator.js

import { body, param } from "express-validator";

export const createNewProductValidator = [
  body("productName").notEmpty().withMessage("productName is required"),
  body("sku").notEmpty().withMessage("sku is required"),
  body("category").notEmpty().withMessage("category is required"),
  body("location").notEmpty().withMessage("location is required"),
  body("initialStatus")
    .notEmpty()
    .isIn(["In Stock", "Out of Stock", "Pending"])
    .withMessage("invalid initialStatus"),
  body("unitCount")
    .isNumeric()
    .withMessage("unitCount must be a number"),
  body("lowStockThreshold")
    .isNumeric()
    .withMessage("lowStockThreshold must be a number")
];

export const updateNewProductValidator = [
  param("id").isMongoId().withMessage("Invalid product ID"),
  body("unitCount").optional().isNumeric(),
  body("lowStockThreshold").optional().isNumeric(),
  body("initialStatus")
    .optional()
    .isIn(["In Stock", "Out of Stock", "Pending"])
];

export const getNewProductByIdValidator = [
  param("id").isMongoId().withMessage("Invalid product ID")
];

export const deleteNewProductValidator = [
  param("id").isMongoId().withMessage("Invalid product ID")
];