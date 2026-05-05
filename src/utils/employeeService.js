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
};

export default employeeService;
