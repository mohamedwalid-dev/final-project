// controllers/employee.controller.js
import Employee from "../models/Employee.js";
import AppError from "../utils/AppError.js";
import { sendSuccess } from "../utils/response.js";

export const createEmployee = async (req, res, next) => {
  try {
    const existingEmployee = await Employee.findOne({ employeeId: req.body.employeeId });
    if (existingEmployee) {
      return res.status(409).json({
        status: "failed",
        data: [],
        message: "Employee ID already exists",
      });
    }

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
      "employeeId",
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

    if (updates.employeeId) {
      const duplicateEmployee = await Employee.findOne({
        employeeId: updates.employeeId,
        _id: { $ne: req.params.id },
      });

      if (duplicateEmployee) {
        return res.status(409).json({
          status: "failed",
          data: [],
          message: "Employee ID already exists",
        });
      }
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

export const createLeaveRequest = async (req, res, next) => {
  try {
    const employee = await Employee.findById(req.params.id);
    if (!employee) {
      throw new AppError("Employee not found", 404);
    }

    const leaveRequest = {
      fullName: req.body.fullName,
      employeeId: req.body.employeeId,
      leaveType: req.body.leaveType,
      leaveBalance: req.body.leaveBalance,
      leaveStartDate: req.body.leaveStartDate,
      leaveEndDate: req.body.leaveEndDate,
      reason: req.body.reason,
      status: "Pending",
    };

    employee.leaveRequests.push(leaveRequest);
    await employee.save();

    return sendSuccess(res, employee.leaveRequests[employee.leaveRequests.length - 1], "Leave request created successfully", 201);
  } catch (error) {
    return next(error);
  }
};

export const getEmployeeLeaveRequests = async (req, res, next) => {
  try {
    const employee = await Employee.findById(req.params.id);
    if (!employee) {
      throw new AppError("Employee not found", 404);
    }

    return sendSuccess(res, employee.leaveRequests || [], "Leave requests fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const updateLeaveRequest = async (req, res, next) => {
  try {
    const employee = await Employee.findById(req.params.id);
    if (!employee) {
      throw new AppError("Employee not found", 404);
    }

    const leaveRequest = employee.leaveRequests.id(req.params.leaveRequestId);
    if (!leaveRequest) {
      throw new AppError("Leave request not found", 404);
    }

    const allowedFields = ["leaveType", "leaveBalance", "leaveStartDate", "leaveEndDate", "reason"];
    const updates = Object.fromEntries(
      Object.entries(req.body).filter(([key]) => allowedFields.includes(key))
    );

    if (Object.keys(updates).length === 0) {
      return sendSuccess(res, leaveRequest, "No fields were updated", 200);
    }

    Object.assign(leaveRequest, updates);
    await employee.save();

    return sendSuccess(res, leaveRequest, "Leave request updated successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const deleteLeaveRequest = async (req, res, next) => {
  try {
    const employee = await Employee.findById(req.params.id);
    if (!employee) {
      throw new AppError("Employee not found", 404);
    }

    const initialLength = employee.leaveRequests.length;
    employee.leaveRequests = employee.leaveRequests.filter((item) => String(item._id) !== String(req.params.leaveRequestId));

    if (employee.leaveRequests.length === initialLength) {
      throw new AppError("Leave request not found", 404);
    }

    await employee.save();
    return sendSuccess(res, [], "Leave request deleted successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const getTeamCapacity = async (req, res, next) => {
  try {
    const employees = await Employee.find().lean();
    const now = new Date();
    const activeEmployees = employees.filter((employee) => {
      const leaveRequests = Array.isArray(employee.leaveRequests) ? employee.leaveRequests : [];
      return leaveRequests.some((request) => {
        const start = request.leaveStartDate ? new Date(request.leaveStartDate) : null;
        const end = request.leaveEndDate ? new Date(request.leaveEndDate) : null;
        return start && end && start <= now && end >= now && request.status !== "Rejected";
      });
    }).length;

    const totalEmployees = employees.length;
    const availableEmployees = Math.max(totalEmployees - activeEmployees, 0);
    const capacityPercent = totalEmployees > 0 ? Math.round((availableEmployees / totalEmployees) * 100) : 0;

    return sendSuccess(res, [{
      dept: "Team",
      pct: capacityPercent,
      color: "#3B5BDB",
      totalEmployees,
      onLeaveEmployees: activeEmployees,
      availableEmployees,
    }], "Team capacity fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};
