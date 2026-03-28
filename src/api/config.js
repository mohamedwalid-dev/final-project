// ─── src/api/config.js ────────────────────────────────────────────────────────
// 🔌 BACKEND CONFIG — Edit these values when connecting your real backend
// All environment variables are read from .env file (Vite prefix: VITE_)
//
// HOW TO USE:
//   1. Copy .env.example → .env.local
//   2. Fill in your backend URL and API key
//   3. All services will automatically use the real API

export const API_CONFIG = {
  // ── Base URL ────────────────────────────────────────────────────────────────
  // Set VITE_API_BASE_URL in your .env file
  // Development:  http://localhost:8000/api
  // Production:   https://your-backend.com/api
  BASE_URL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api",

  // ── Auth ────────────────────────────────────────────────────────────────────
  // The header name your backend expects for the JWT token
  AUTH_HEADER: "Authorization",
  AUTH_PREFIX: "Bearer",         // e.g. "Bearer <token>"  — change to "Token" for DRF

  // ── Timeouts ────────────────────────────────────────────────────────────────
  DEFAULT_TIMEOUT_MS: 15_000,    // 15s request timeout
  UPLOAD_TIMEOUT_MS:  60_000,    // 60s for file uploads

  // ── Pagination ──────────────────────────────────────────────────────────────
  DEFAULT_PAGE_SIZE: 20,

  // ── API version prefix ──────────────────────────────────────────────────────
  API_VERSION: import.meta.env.VITE_API_VERSION ?? "v1",

  // ── Feature flags ───────────────────────────────────────────────────────────
  // Set to false to disable mock data and use real API only
  USE_MOCK: import.meta.env.VITE_USE_MOCK !== "false",
};

// Convenience: full versioned base path → e.g. http://localhost:8000/api/v1
export const API_BASE = `${API_CONFIG.BASE_URL}/${API_CONFIG.API_VERSION}`;

// ── Endpoint registry ─────────────────────────────────────────────────────────
// Single source of truth for all backend endpoints.
// Change these once here if your backend routes change.
export const ENDPOINTS = {
  // Auth
  AUTH: {
    LOGIN:          "/auth/login",
    LOGOUT:         "/auth/logout",
    REFRESH:        "/auth/refresh",
    ME:             "/auth/me",
    RESET_PASSWORD: "/auth/reset-password",
  },

  // Dashboard
  DASHBOARD: {
    KPIs:           "/dashboard/kpis",
    REVENUE_CHART:  "/dashboard/revenue-chart",
    RECENT:         "/dashboard/recent-activity",
  },

  // Finance
  FINANCE: {
    STATS:          "/finance/stats",
    TRANSACTIONS:   "/finance/transactions",
    CASH_FLOW:      "/finance/cash-flow",
  },

  // Invoices
  INVOICES: {
    LIST:           "/invoices",
    DETAIL:         (id) => `/invoices/${id}`,
    STATS:          "/invoices/stats",
    CREATE:         "/invoices",
    UPDATE:         (id) => `/invoices/${id}`,
    STATUS:         (id) => `/invoices/${id}/status`,
    DELETE:         (id) => `/invoices/${id}`,
    BULK_DELETE:    "/invoices/bulk-delete",
    EXPORT:         "/invoices/export",
  },

  // HR
  HR: {
    EMPLOYEES:      "/hr/employees",
    EMPLOYEE:       (id) => `/hr/employees/${id}`,
    STATS:          "/hr/stats",
    DEPARTMENTS:    "/hr/departments",
    PAYROLL:        "/hr/payroll",
    LEAVE:          "/hr/leave-requests",
  },

  // Inventory
  INVENTORY: {
    PRODUCTS:       "/inventory/products",
    PRODUCT:        (id) => `/inventory/products/${id}`,
    STATS:          "/inventory/stats",
    WAREHOUSES:     "/inventory/warehouses",
    ALERTS:         "/inventory/alerts",
    LIVE_FEED:      "/inventory/live-feed",
  },

  // Sales & CRM
  SALES: {
    LEADS:          "/sales/leads",
    LEAD:           (id) => `/sales/leads/${id}`,
    STATS:          "/sales/stats",
    PIPELINE:       "/sales/pipeline",
    ACTIVITIES:     "/sales/activities",
  },

  // Support
  SUPPORT: {
    TICKETS:        "/support/tickets",
    TICKET:         (id) => `/support/tickets/${id}`,
    MESSAGES:       (id) => `/support/tickets/${id}/messages`,
    ASSIGN:         (id) => `/support/tickets/${id}/assign`,
    STATUS:         (id) => `/support/tickets/${id}/status`,
    STATS:          "/support/stats",
  },
};
