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
    .withMessage("lowStockThreshold must be a number"),
  body("price")
    .exists({ checkFalsy: true })
    .withMessage("Product price is required")
    .bail()
    .isFloat({ min: 0 })
    .withMessage("Product price must be a valid number greater than or equal to 0")
    .toFloat(),
];

export const updateNewProductValidator = [
  param("id").isMongoId().withMessage("Invalid product ID"),
  body("unitCount").optional().isNumeric(),
  body("lowStockThreshold").optional().isNumeric(),
  body("initialStatus")
    .optional()
    .isIn(["In Stock", "Out of Stock", "Pending"]),
  body("price")
    .optional()
    .isFloat({ min: 0 })
    .withMessage("Product price must be a valid number greater than or equal to 0")
    .toFloat(),
];

export const getNewProductByIdValidator = [
  param("id").isMongoId().withMessage("Invalid product ID")
];

export const deleteNewProductValidator = [
  param("id").isMongoId().withMessage("Invalid product ID")
];