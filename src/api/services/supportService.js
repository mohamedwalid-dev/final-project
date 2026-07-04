// ─── src/api/services/supportService.js ──────────────────────────────────────
// Support / Tickets service
// All methods return { data, error } — matches existing pattern.
//
// 🔌 TO CONNECT BACKEND:
//   1. Set VITE_USE_MOCK=false in .env.local
//   2. Replace each mock block with the http.* call in the 🔌 SWAP comment
//   3. No changes needed in SupportPage.jsx

import { fetchSafe } from "../client";
import { http }       from "../client";
import { ENDPOINTS }  from "../config";
import { API_CONFIG } from "../config";

// ── MOCK DATA (used when VITE_USE_MOCK=true) ──────────────────────────────────
const _TICKETS = [
  { id: "TK-4821", name: "Sarah Jenkins",  priority: "urgent", status: "open",    subject: "Issue with license key renewal",  createdAt: "2024-10-24T10:14:00Z" },
  { id: "TK-4789", name: "Marcus Thorne",  priority: "high",   status: "pending", subject: "Data export taking too long",       createdAt: "2024-10-24T09:30:00Z" },
  { id: "TK-4785", name: "Elena Rodriguez",priority: "medium", status: "pending", subject: "Invoice #INV-2024-001 Query",       createdAt: "2024-10-24T08:00:00Z" },
  { id: "TK-4780", name: "David Kim",      priority: "urgent", status: "open",    subject: "Access denied to HR module",        createdAt: "2024-10-24T07:00:00Z" },
];

const _STATS = { open: 12, pending: 8, resolved: 142, avgResponseMin: 14 };

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const supportService = {
  /**
   * Get all tickets (with optional filters).
   * 🔌 SWAP: return http.get(ENDPOINTS.SUPPORT.TICKETS, filters, signal);
   */
  fetchTickets: (filters = {}, signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) {
        const res = await http.get(ENDPOINTS.SUPPORT.TICKETS, filters, signal);
        return res.data;
      }
      await delay(250);
      return _TICKETS;
    }),

  /**
   * Get single ticket detail.
   * 🔌 SWAP: return http.get(ENDPOINTS.SUPPORT.TICKET(id), {}, signal);
   */
  fetchTicket: (id, signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) {
        const res = await http.get(ENDPOINTS.SUPPORT.TICKET(id), {}, signal);
        return res.data;
      }
      await delay(150);
      const ticket = _TICKETS.find((t) => t.id === id);
      if (!ticket) throw new Error(`Ticket ${id} not found`);
      return ticket;
    }),

  /**
   * Send a reply message.
   * 🔌 SWAP: return http.post(ENDPOINTS.SUPPORT.MESSAGES(ticketId), { text, from: "agent" });
   */
  sendMessage: (ticketId, text) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) {
        const res = await http.post(ENDPOINTS.SUPPORT.MESSAGES(ticketId), { text, from: "agent" });
        return res.data;
      }
      await delay(300);
      return { id: "m" + Date.now(), from: "agent", text, time: new Date().toISOString() };
    }),

  /**
   * Create a new ticket.
   * 🔌 SWAP: return http.post(ENDPOINTS.SUPPORT.TICKETS, payload);
   */
  createTicket: (payload) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) {
        const res = await http.post(ENDPOINTS.SUPPORT.TICKETS, payload);
        return res.data;
      }
      await delay(600);
      return { id: `TK-${Date.now().toString().slice(-4)}`, status: "open", ...payload };
    }),

  /**
   * Update ticket status.
   * 🔌 SWAP: return http.patch(ENDPOINTS.SUPPORT.STATUS(id), { status });
   */
  updateStatus: (id, status) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) {
        const res = await http.patch(ENDPOINTS.SUPPORT.STATUS(id), { status });
        return res.data;
      }
      await delay(200);
      return { id, status };
    }),

  /**
   * Fetch support stats / KPIs.
   * 🔌 SWAP: return http.get(ENDPOINTS.SUPPORT.STATS);
   */
  fetchStats: (signal) =>
    fetchSafe(async () => {
      if (!API_CONFIG.USE_MOCK) {
        const res = await http.get(ENDPOINTS.SUPPORT.STATS, {}, signal);
        return res.data;
      }
      await delay(150);
      return _STATS;
    }),
};

export default supportService;
