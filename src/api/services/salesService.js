// ─── src/api/services/salesService.js ────────────────────────────────────────
// Sales & CRM service — Leads, Pipeline, Activities

import { fetchSafe }  from "../client";
import { http }       from "../client";
import { ENDPOINTS }  from "../config";
import { API_CONFIG } from "../config";

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const salesService = {
  /** 🔌 SWAP: return http.get(ENDPOINTS.SALES.STATS, {}, signal); */
  fetchStats: (signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.SALES.STATS,{},signal); return r.data; }
      await delay(200);
      return { totalLeads: 284, converted: 47, pipeline: "$1.2M", winRate: "22%" };
    }),

  /** 🔌 SWAP: return http.get(ENDPOINTS.SALES.LEADS, filters, signal); */
  fetchLeads: (filters = {}, signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.SALES.LEADS, filters, signal); return r.data; }
      await delay(300); return [];
    }),

  /** 🔌 SWAP: return http.post(ENDPOINTS.SALES.LEADS, payload); */
  createLead: (payload) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.post(ENDPOINTS.SALES.LEADS, payload); return r.data; }
      await delay(500); return { id: "L" + Date.now(), ...payload, status: "New" };
    }),

  /** 🔌 SWAP: return http.patch(ENDPOINTS.SALES.LEAD(id), updates); */
  updateLead: (id, updates) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.patch(ENDPOINTS.SALES.LEAD(id), updates); return r.data; }
      await delay(250); return { id, ...updates };
    }),

  /** 🔌 SWAP: return http.get(ENDPOINTS.SALES.PIPELINE, {}, signal); */
  fetchPipeline: (signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.SALES.PIPELINE,{},signal); return r.data; }
      await delay(300); return [];
    }),

  /** 🔌 SWAP: return http.get(ENDPOINTS.SALES.ACTIVITIES, filters, signal); */
  fetchActivities: (filters = {}, signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.SALES.ACTIVITIES, filters, signal); return r.data; }
      await delay(200); return [];
    }),
};

export default salesService;
