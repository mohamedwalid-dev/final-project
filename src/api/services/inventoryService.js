// ─── src/api/services/inventoryService.js ─────────────────────────────────────
// Inventory service
// All methods return { data, error }.
//
// 🔌 TO CONNECT BACKEND: set VITE_USE_MOCK=false and swap each mock block.

import { fetchSafe }  from "../client";
import { http }       from "../client";
import { ENDPOINTS }  from "../config";
import { API_CONFIG } from "../config";

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const _STATS = {
  totalAssets: "$2,845,000", stockTurnover: "4.2x", utilization: "78.4%", lowStock: 14,
};
const _PRODUCTS = [
  { id:"p1", name:"Quantum Processor X1",  sku:"SYN-Q100", location:"Warehouse A-12", stockPct:85, status:"Healthy",  units:850, threshold:100 },
  { id:"p2", name:"Nebula Glass Screen",   sku:"SYN-N550", location:"Warehouse B-04", stockPct:12, status:"Critical", units:12,  threshold:50  },
  { id:"p3", name:"Titanium Chassis V2",   sku:"SYN-T600", location:"Central Hub",    stockPct:45, status:"Warning",  units:225, threshold:80  },
];

const inventoryService = {
  /** 🔌 SWAP: return http.get(ENDPOINTS.INVENTORY.STATS, {}, signal); */
  fetchStats: (signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.INVENTORY.STATS,{},signal); return r.data; }
      await delay(200); return _STATS;
    }),

  /** 🔌 SWAP: return http.get(ENDPOINTS.INVENTORY.PRODUCTS, filters, signal); */
  fetchProducts: (filters = {}, signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.INVENTORY.PRODUCTS, filters, signal); return r.data; }
      await delay(300); return _PRODUCTS;
    }),

  /** 🔌 SWAP: return http.post(ENDPOINTS.INVENTORY.PRODUCTS, payload); */
  addProduct: (payload) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.post(ENDPOINTS.INVENTORY.PRODUCTS, payload); return r.data; }
      await delay(600); return { id: "p" + Date.now(), ...payload };
    }),

  /** 🔌 SWAP: return http.patch(ENDPOINTS.INVENTORY.PRODUCT(id), updates); */
  updateProduct: (id, updates) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.patch(ENDPOINTS.INVENTORY.PRODUCT(id), updates); return r.data; }
      await delay(300); return { id, ...updates };
    }),

  /** 🔌 SWAP: return http.delete(ENDPOINTS.INVENTORY.PRODUCT(id)); */
  deleteProduct: (id) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.delete(ENDPOINTS.INVENTORY.PRODUCT(id)); return r.data; }
      await delay(300); return { success: true };
    }),

  /** 🔌 SWAP: return http.get(ENDPOINTS.INVENTORY.WAREHOUSES, {}, signal); */
  fetchWarehouses: (signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.INVENTORY.WAREHOUSES,{},signal); return r.data; }
      await delay(200); return [];
    }),

  /** 🔌 SWAP: return http.get(ENDPOINTS.INVENTORY.ALERTS, {}, signal); */
  fetchAlerts: (signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) { const r = await http.get(ENDPOINTS.INVENTORY.ALERTS,{},signal); return r.data; }
      await delay(150); return [];
    }),
};

export default inventoryService;
