// ─── src/api/index.js ─────────────────────────────────────────────────────────
// Barrel export — import everything from "@api" or "../../api"
//
// Usage example in any page:
//   import { supportService, useApi } from "../../api";
//   const { data, loading } = useApi((signal) => supportService.fetchTickets({}, signal));

export { default as authService }      from "./auth";
export { default as supportService }   from "./services/supportService";
export { default as inventoryService } from "./services/inventoryService";
export { default as salesService }     from "./services/salesService";
export { default as dashboardService } from "./services/dashboardService";

export { http, fetchSafe }            from "./client";
export { API_CONFIG, API_BASE, ENDPOINTS } from "./config";
export { tokenStorage }               from "./auth";

// Re-export hooks for convenience
export { useApi, useMutation }        from "../hooks/useApi";
