// ─── utils/employeeService.js ──────────────────────────────────────────────────
import { http } from "../api/client";
import { ENDPOINTS } from "../api/endpoints";

const employeeService = {
  // Fetch all employees
  fetchEmployees: async (signal) => {
    try {
      const result = await http.get(ENDPOINTS.EMPLOYEES.LIST, { signal });
      if (result.error) return { data: null, error: result.error };
      const employees = Array.isArray(result.data?.data) ? result.data.data : [];
      return { data: employees, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch employees" };
    }
  },

  // Create employee
  createEmployee: async (payload) => {
    try {
      const result = await http.post(ENDPOINTS.EMPLOYEES.CREATE, payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to create employee" };
    }
  },

  // Get employee by ID
  getEmployee: async (id) => {
    try {
      const result = await http.get(ENDPOINTS.EMPLOYEES.DETAIL(id));
      if (result.error) return { data: null, error: result.error };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch employee" };
    }
  },

  // Update employee
  updateEmployee: async (id, payload) => {
    try {
      const result = await http.patch(ENDPOINTS.EMPLOYEES.UPDATE(id), payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to update employee" };
    }
  },

  // Delete employee
  deleteEmployee: async (id) => {
    try {
      const result = await http.delete(ENDPOINTS.EMPLOYEES.DELETE(id));
      if (result.error) return { data: null, error: result.error };
      return { data: true, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to delete employee" };
    }
  },

  // Fetch leave requests for employee
  fetchEmployeeLeaveRequests: async (id, signal) => {
    try {
      const result = await http.get(ENDPOINTS.EMPLOYEES.LEAVE_REQUESTS(id), { signal });
      if (result.error) return { data: null, error: result.error };
      const leaveRequests = Array.isArray(result.data?.data) ? result.data.data : [];
      return { data: leaveRequests, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch leave requests" };
    }
  },

  // Create leave request for employee
  createLeaveRequest: async (id, payload) => {
    try {
      const result = await http.post(ENDPOINTS.EMPLOYEES.LEAVE_REQUESTS(id), payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to create leave request" };
    }
  },

  // Update leave request for employee
  updateLeaveRequest: async (employeeId, leaveRequestId, payload) => {
    try {
      const result = await http.patch(ENDPOINTS.EMPLOYEES.LEAVE_REQUEST(employeeId, leaveRequestId), payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to update leave request" };
    }
  },

  // Delete leave request for employee
  deleteLeaveRequest: async (employeeId, leaveRequestId) => {
    try {
      const result = await http.delete(ENDPOINTS.EMPLOYEES.LEAVE_REQUEST(employeeId, leaveRequestId));
      if (result.error) return { data: null, error: result.error };
      return { data: true, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to delete leave request" };
    }
  },

  // Fetch team capacity statistics
  fetchTeamCapacity: async (signal) => {
    try {
      const result = await http.get(ENDPOINTS.EMPLOYEES.TEAM_CAPACITY, { signal });
      if (result.error) return { data: null, error: result.error };
      const teamCapacity = Array.isArray(result.data?.data) ? result.data.data : [];
      return { data: teamCapacity, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch team capacity" };
    }
  },
};

export default employeeService;
