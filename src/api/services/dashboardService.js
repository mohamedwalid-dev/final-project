// ─── src/api/services/dashboardService.js ────────────────────────────────────
// Dashboard KPIs + charts service

import { fetchSafe }  from "../client";
import { http }       from "../client";
import { ENDPOINTS }  from "../config";
import { API_CONFIG } from "../config";

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const dashboardService = {
  /** 🔌 SWAP: return http.get(ENDPOINTS.DASHBOARD.KPIs, {}, signal); */
  fetchKPIs: (signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.DASHBOARD.KPIs,{},signal); return r.data; }
      await delay(250);
      return {
        revenue:   { value: "$284,500", change: "+12.8%", up: true },
        customers: { value: "1,284",    change: "+8.2%",  up: true },
        invoices:  { value: "248",      change: "-2.1%",  up: false},
        expenses:  { value: "$48,200",  change: "+5.4%",  up: false},
      };
    }),

  /** 🔌 SWAP: return http.get(ENDPOINTS.DASHBOARD.REVENUE_CHART, { period }, signal); */
  fetchRevenueChart: (period = "monthly", signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.DASHBOARD.REVENUE_CHART,{period},signal); return r.data; }
      await delay(350);
      return [42, 58, 74, 66, 89, 95, 78, 103, 112, 98, 120, 135].map((v, i) => ({
        label: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][i],
        value: v * 1000,
      }));
    }),

  /** 🔌 SWAP: return http.get(ENDPOINTS.DASHBOARD.RECENT, {}, signal); */
  fetchRecentActivity: (signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.DASHBOARD.RECENT,{},signal); return r.data; }
      await delay(200); return [];
    }),
};

export default dashboardService;
