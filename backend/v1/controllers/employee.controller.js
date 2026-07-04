// controllers/employee.controller.js
import Employee from "../models/Employee.js";
import AppError from "../utils/AppError.js";
import { sendSuccess } from "../utils/response.js";

export const createEmployee = async (req, res, next) => {
  try {
    const employee = await Employee.create(req.body);
    return sendSuccess(res, employee, "Employee created successfully", 201);
  } catch (error) {
    return next(error);
  }
};

export const getAllEmployees = async (req, res, next) => {
  try {
    const employees = await Employee.find().sort({ createdAt: -1 });
    return sendSuccess(res, employees, "Employees fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const getEmployeeById = async (req, res, next) => {
  try {
    const employee = await Employee.findById(req.params.id);
    if (!employee) {
      throw new AppError("Employee not found", 404);
    }
    return sendSuccess(res, employee, "Employee fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const updateEmployee = async (req, res, next) => {
  try {
    const allowedFields = [
      "fullName",
      "department",
      "jobTitle",
      "location",
      "workEmail",
      "salary",
      "phoneNumber",
      "startDate",
      "dateOfBirth",
      "gender",
    ];

    const updates = Object.fromEntries(
      Object.entries(req.body).filter(([key]) => allowedFields.includes(key))
    );

    if (Object.keys(updates).length === 0) {
      return sendSuccess(res, [], "No fields were updated", 200);
    }

    const employee = await Employee.findByIdAndUpdate(req.params.id, updates, {
      new: true,
      runValidators: true,
    });

    if (!employee) {
      throw new AppError("Employee not found", 404);
    }

    return sendSuccess(res, employee, "Employee updated successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const deleteEmployee = async (req, res, next) => {
  try {
    const employee = await Employee.findByIdAndDelete(req.params.id);

    if (!employee) {
      throw new AppError("Employee not found", 404);
    }

    return sendSuccess(res, [], "Employee deleted successfully", 200);
  } catch (error) {
    return next(error);
  }
};
