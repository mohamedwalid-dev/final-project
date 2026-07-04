// validators/employee.validator.js
import { body, param } from "express-validator";

const phoneRegex = /^\+?[0-9\s()-]{7,15}$/;
const genderOptions = ["Male", "Female", "Prefer not to say"];

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
  body("salary")
    .notEmpty()
    .withMessage("Salary is required")
    .isFloat({ min: 0 })
    .withMessage("Salary must be a number greater than or equal to 0"),
  body("phoneNumber")
    .notEmpty()
    .withMessage("Phone number is required")
    .matches(phoneRegex)
    .withMessage("Phone number must be a valid phone format"),
  body("startDate")
    .notEmpty()
    .withMessage("Start date is required")
    .isISO8601()
    .withMessage("Start date must be a valid date"),
  body("dateOfBirth")
    .notEmpty()
    .withMessage("Date of birth is required")
    .isISO8601()
    .withMessage("Date of birth must be a valid date"),
  body("gender")
    .notEmpty()
    .withMessage("Gender is required")
    .isIn(genderOptions)
    .withMessage("Gender must be Male, Female, or Prefer not to say"),
];

export const updateEmployeeValidator = [
  param("id").isMongoId().withMessage("Invalid ID"),
  body("fullName").optional().notEmpty().withMessage("Full name cannot be empty"),
  body("department").optional().notEmpty().withMessage("Department cannot be empty"),
  body("jobTitle").optional().notEmpty().withMessage("Job title cannot be empty"),
  body("location").optional().notEmpty().withMessage("Location cannot be empty"),
  body("workEmail").optional().isEmail().withMessage("Invalid email"),
  body("salary")
    .optional({ values: "falsy" })
    .isFloat({ min: 0 })
    .withMessage("Salary must be a number greater than or equal to 0"),
  body("phoneNumber")
    .optional({ values: "falsy" })
    .matches(phoneRegex)
    .withMessage("Phone number must be a valid phone format"),
  body("startDate")
    .optional({ values: "falsy" })
    .isISO8601()
    .withMessage("Start date must be a valid date"),
  body("dateOfBirth")
    .optional({ values: "falsy" })
    .isISO8601()
    .withMessage("Date of birth must be a valid date"),
  body("gender")
    .optional({ values: "falsy" })
    .isIn(genderOptions)
    .withMessage("Gender must be Male, Female, or Prefer not to say"),
];

export const getEmployeeValidator = [
  param("id").isMongoId().withMessage("Invalid ID"),
];

export const deleteEmployeeValidator = [
  param("id").isMongoId().withMessage("Invalid ID"),
];