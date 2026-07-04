// routes/employee.routes.js
import express from "express";
import {
  createEmployee,
  getAllEmployees,
  getEmployeeById,
  updateEmployee,
  deleteEmployee,
  createLeaveRequest,
  getEmployeeLeaveRequests,
  updateLeaveRequest,
  deleteLeaveRequest,
  getTeamCapacity,
} from "../controllers/employee.controller.js";

import {
  createEmployeeValidator,
  updateEmployeeValidator,
  getEmployeeValidator,
  deleteEmployeeValidator,
  createLeaveRequestValidator,
} from "../middleware/employee.validator.js";

import { sanitizeEmployeePayload, validate } from "../middleware/employee.middleware.js";

const router = express.Router();

router.post("/", sanitizeEmployeePayload, createEmployeeValidator, validate, createEmployee);
router.get("/", getAllEmployees);
router.get("/team-capacity", getTeamCapacity);
router.get("/:id", getEmployeeValidator, validate, getEmployeeById);
router.get("/:id/leave-requests", getEmployeeValidator, validate, getEmployeeLeaveRequests);
router.post("/:id/leave-requests", sanitizeEmployeePayload, createLeaveRequestValidator, validate, createLeaveRequest);
router.patch("/:id/leave-requests/:leaveRequestId", sanitizeEmployeePayload, createLeaveRequestValidator, validate, updateLeaveRequest);
router.delete("/:id/leave-requests/:leaveRequestId", deleteEmployeeValidator, validate, deleteLeaveRequest);
router.put("/:id", sanitizeEmployeePayload, updateEmployeeValidator, validate, updateEmployee);
router.patch("/:id", sanitizeEmployeePayload, updateEmployeeValidator, validate, updateEmployee);
router.delete("/:id", deleteEmployeeValidator, validate, deleteEmployee);

export default router;
