// ─── utils/leadService.js ──────────────────────────────────────────────────
import { http } from "../api/client";
import { ENDPOINTS } from "../api/endpoints";

const leadService = {
  // Fetch all leads
  fetchLeads: async (signal) => {
    try {
      const result = await http.get(ENDPOINTS.LEADS.LIST, { signal });
      if (result.error) return { data: null, error: result.error };
      const leads = Array.isArray(result.data?.data) ? result.data.data : [];
      return { data: leads, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch leads" };
    }
  },

  // Create lead
  createLead: async (payload) => {
    try {
      const result = await http.post(ENDPOINTS.LEADS.CREATE, payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to create lead" };
    }
  },

  // Get lead by ID
  getLead: async (id) => {
    try {
      const result = await http.get(ENDPOINTS.LEADS.DETAIL(id));
      if (result.error) return { data: null, error: result.error };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch lead" };
    }
  },

  // Update lead
  updateLead: async (id, payload) => {
    try {
      const result = await http.patch(ENDPOINTS.LEADS.UPDATE(id), payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to update lead" };
    }
  },

  // Delete lead
  deleteLead: async (id) => {
    try {
      const result = await http.delete(ENDPOINTS.LEADS.DELETE(id));
      if (result.error) return { data: null, error: result.error };
      return { data: true, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to delete lead" };
    }
  },
};

export default leadService;
