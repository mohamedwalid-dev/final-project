// validators/employee.validator.js
import { body, param } from "express-validator";

export const createEmployeeValidator = [
  body("fullName").notEmpty().withMessage("Full name is required"),
  body("department").notEmpty().withMessage("Department is required"),
  body("jobTitle").notEmpty().withMessage("Job title is required"),
  body("location").notEmpty().withMessage("Location is required"),
  body("workEmail")
    .notEmpty()
    .withMessage("Email is required")
    .isEmail()
    .withMessage("Invalid email format"),
];

export const updateEmployeeValidator = [
  param("id").isMongoId().withMessage("Invalid ID"),
  body("fullName").optional().notEmpty(),
  body("department").optional().notEmpty(),
  body("jobTitle").optional().notEmpty(),
  body("location").optional().notEmpty(),
  body("workEmail").optional().isEmail().withMessage("Invalid email"),
];

export const getEmployeeValidator = [
  param("id").isMongoId().withMessage("Invalid ID"),
];

export const deleteEmployeeValidator = [
  param("id").isMongoId().withMessage("Invalid ID"),
];