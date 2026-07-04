// validators/employee.validator.js
import { body, param } from "express-validator";

const phoneRegex = /^\+?[0-9\s()-]{7,15}$/;
const genderOptions = ["Male", "Female", "Prefer not to say"];

export const createEmployeeValidator = [
  body("fullName").notEmpty().withMessage("Full name is required"),
  body("employeeId")
    .notEmpty()
    .withMessage("Employee ID is required")
    .isString()
    .withMessage("Employee ID must be a string")
    .trim()
    .isLength({ max: 30 })
    .withMessage("Employee ID must be at most 30 characters"),
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
  body("employeeId")
    .optional({ values: "falsy" })
    .isString()
    .withMessage("Employee ID must be a string")
    .trim()
    .isLength({ max: 30 })
    .withMessage("Employee ID must be at most 30 characters"),
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

export const createLeaveRequestValidator = [
  body("fullName").notEmpty().withMessage("Full name is required"),
  body("employeeId").notEmpty().withMessage("Employee ID is required"),
  body("leaveType")
    .notEmpty()
    .withMessage("Leave type is required")
    .isIn(["Annual Leave", "Sick Leave", "Emergency Leave", "Unpaid Leave", "Maternity Leave", "Paternity Leave", "Other"])
    .withMessage("Leave type is invalid"),
  body("leaveBalance")
    .notEmpty()
    .withMessage("Leave balance is required")
    .isFloat({ min: 0 })
    .withMessage("Leave balance must be numeric"),
  body("leaveStartDate")
    .notEmpty()
    .withMessage("Leave start date is required")
    .isISO8601()
    .withMessage("Leave start date must be a valid date"),
  body("leaveEndDate")
    .notEmpty()
    .withMessage("Leave end date is required")
    .isISO8601()
    .withMessage("Leave end date must be a valid date")
    .custom((value, { req }) => {
      if (new Date(value) < new Date(req.body.leaveStartDate)) {
        throw new Error("Leave end date cannot be earlier than leave start date");
      }
      return true;
    }),
  body("reason").notEmpty().withMessage("Reason is required"),
];

export const getEmployeeValidator = [
  param("id").isMongoId().withMessage("Invalid ID"),
];

export const deleteEmployeeValidator = [
  param("id").isMongoId().withMessage("Invalid ID"),
];