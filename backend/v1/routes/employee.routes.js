// routes/employee.routes.js
import express from "express";
import {
  createEmployee,
  getAllEmployees,
  getEmployeeById,
  updateEmployee,
  deleteEmployee,
} from "../controllers/employee.controller.js";

import {
  createEmployeeValidator,
  updateEmployeeValidator,
  getEmployeeValidator,
  deleteEmployeeValidator,
} from "../middleware/employee.validator.js";

import { validate } from "../middleware/employee.middleware.js";

const router = express.Router();

router.post("/", createEmployeeValidator, validate, createEmployee);
router.get("/", getAllEmployees);
router.get("/:id", getEmployeeValidator, validate, getEmployeeById);
router.put("/:id", updateEmployeeValidator, validate, updateEmployee);
router.patch("/:id", updateEmployeeValidator, validate, updateEmployee);
router.delete("/:id", deleteEmployeeValidator, validate, deleteEmployee);

export default router;
