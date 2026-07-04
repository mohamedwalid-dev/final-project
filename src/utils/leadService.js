// ─── utils/leadService.js ──────────────────────────────────────────────────
import { http } from "../api/client";
import { ENDPOINTS } from "../api/endpoints";

const leadService = {
  // Fetch all leads
  fetchLeads: async (signal) => {
    try {
      const result = await http.get(ENDPOINTS.LEADS.LIST, { signal });
      if (result.error) return { data: null, analytics: null, error: result.error };
      const leads = Array.isArray(result.data?.data) ? result.data.data : [];
      const analytics = result.data?.analytics || null;
      return { data: leads, analytics, error: null };
    } catch (err) {
      return { data: null, analytics: null, error: err.message || "Failed to fetch leads" };
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

  getProductSuggestions: async (query) => {
    try {
      const result = await http.get(ENDPOINTS.LEADS.PRODUCT_SUGGESTIONS, { params: { q: query } });
      if (result.error) return { data: null, error: result.error };
      return { data: result.data?.data || [], error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch suggestions" };
    }
  },

  addProductToLead: async (id, payload) => {
    try {
      const result = await http.post(ENDPOINTS.LEADS.PRODUCTS(id), payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to add product to lead" };
    }
  },

  updateLeadProduct: async (leadId, productId, payload) => {
    try {
      const result = await http.put(ENDPOINTS.LEADS.PRODUCT_DETAIL(leadId, productId), payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to update product" };
    }
  },

  deleteLeadProduct: async (leadId, productId) => {
    try {
      const result = await http.delete(ENDPOINTS.LEADS.PRODUCT_DETAIL(leadId, productId));
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to delete product" };
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
