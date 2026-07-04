// middleware/employee.middleware.js
import { validationResult } from "express-validator";

export const sanitizeEmployeePayload = (req, _res, next) => {
  if (!req.body || typeof req.body !== "object") {
    return next();
  }

  const payload = { ...req.body };

  if (payload.fullName !== undefined) payload.fullName = payload.fullName.trim();
  if (payload.department !== undefined) payload.department = payload.department.trim();
  if (payload.jobTitle !== undefined) payload.jobTitle = payload.jobTitle.trim();
  if (payload.location !== undefined) payload.location = payload.location.trim();
  if (payload.workEmail !== undefined) payload.workEmail = payload.workEmail.trim();
  if (payload.phoneNumber !== undefined) payload.phoneNumber = payload.phoneNumber.trim();
  if (payload.gender !== undefined) payload.gender = payload.gender.trim();

  if (payload.salary !== undefined && payload.salary !== "") {
    payload.salary = Number(payload.salary);
  }

  req.body = payload;
  next();
};

export const validate = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({
      status: "failed",
      data: errors.array(),
      message: "Validation error",
    });
  }
  next();
};