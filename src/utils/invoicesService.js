// ─── utils/invoicesService.js ──────────────────────────────────────────────────
// Service layer for invoices - connects to real backend API endpoints
// ✅ No mock data - all real API calls
// ✅ AbortController support
// ✅ Normalized error handling
// ✅ Supports invoice status: Paid / Pending / Overdue

import { http } from "../api/client";
import { ENDPOINTS } from "../api/endpoints";

const ALLOWED_STATUSES = ["Paid", "Pending", "Overdue"];

const normalizeInvoiceStatus = (status) => {
  return ALLOWED_STATUSES.includes(status) ? status : "Pending";
};

const getInvoiceTotal = (invoice) => {
  if (!invoice) return 0;

  if (typeof invoice.total === "number") return invoice.total;
  if (typeof invoice.grandTotal === "number") return invoice.grandTotal;

  if (Array.isArray(invoice.lineItems)) {
    return invoice.lineItems.reduce((sum, item) => {
      return sum + (Number(item.total) || 0);
    }, 0);
  }

  return 0;
};

const normalizeInvoice = (invoice) => {
  if (!invoice) return invoice;

  return {
    ...invoice,
    status: normalizeInvoiceStatus(invoice.status),
    totalAmount: getInvoiceTotal(invoice),
  };
};

const invoicesService = {
  // Fetch all invoices
  fetchInvoices: async (filters = {}, signal) => {
    try {
      const result = await http.get(ENDPOINTS.INVOICES.LIST, { signal });

      if (result.error) {
        return { data: null, error: result.error };
      }

      let invoices = Array.isArray(result.data?.data)
        ? result.data.data.map(normalizeInvoice)
        : [];

      // Apply status filter using real API status value
      if (filters.status && filters.status !== "All") {
        invoices = invoices.filter((inv) => inv.status === filters.status);
      }

      // Apply search filter
      if (filters.q) {
        const q = filters.q.toLowerCase();

        invoices = invoices.filter((inv) => {
          const customerName =
            inv.clientInformation?.customerName?.toLowerCase() || "";

          const invoiceId = inv._id?.toLowerCase() || "";

          const poNumber =
            inv.invoiceTimeline?.poNumber?.toLowerCase() || "";

          return (
            customerName.includes(q) ||
            invoiceId.includes(q) ||
            poNumber.includes(q)
          );
        });
      }

      return { data: invoices, error: null };
    } catch (err) {
      return {
        data: null,
        error: err.message || "Failed to fetch invoices",
      };
    }
  },

  // Fetch invoice stats
  fetchInvoiceStats: async (signal) => {
    try {
      const result = await http.get(ENDPOINTS.INVOICES.LIST, { signal });

      if (result.error) {
        return { data: null, error: result.error };
      }

      const invoices = Array.isArray(result.data?.data)
        ? result.data.data.map(normalizeInvoice)
        : [];

      const totalInvoiced = invoices.reduce((sum, inv) => {
        return sum + getInvoiceTotal(inv);
      }, 0);

      const received = invoices
        .filter((inv) => inv.status === "Paid")
        .reduce((sum, inv) => {
          return sum + getInvoiceTotal(inv);
        }, 0);

      const overdue = invoices
        .filter((inv) => inv.status === "Overdue")
        .reduce((sum, inv) => {
          return sum + getInvoiceTotal(inv);
        }, 0);

      const outstanding = invoices
        .filter((inv) => inv.status === "Pending" || inv.status === "Overdue")
        .reduce((sum, inv) => {
          return sum + getInvoiceTotal(inv);
        }, 0);

      return {
        data: {
          totalInvoiced,
          outstanding,
          received,
          overdue,
        },
        error: null,
      };
    } catch (err) {
      return {
        data: null,
        error: err.message || "Failed to fetch stats",
      };
    }
  },

  // Fetch single invoice
  fetchInvoiceById: async (id, signal) => {
    try {
      const result = await http.get(ENDPOINTS.INVOICES.DETAIL(id), { signal });

      console.log("fetchInvoiceById raw result:", result);

      if (result.error) {
        return { data: null, error: result.error };
      }

      const resultData = result.data?.data !== undefined ? result.data.data : result.data;
      const invoice = Array.isArray(resultData) ? resultData[0] : resultData;

      if (!invoice) {
        return {
          data: null,
          error: "Invoice not found",
        };
      }

      return {
        data: normalizeInvoice(invoice),
        error: null,
      };
    } catch (err) {
      return {
        data: null,
        error: err.message || "Failed to fetch invoice",
      };
    }
  },
  // Create invoice
  createInvoice: async (payload) => {
    try {
      const normalizedPayload = {
        ...payload,
        status: normalizeInvoiceStatus(payload.status),
      };

      const result = await http.post(
        ENDPOINTS.INVOICES.CREATE,
        normalizedPayload
      );

      if (result.error) {
        return {
          data: null,
          error: result.error,
          errorData: result.errorData,
        };
      }

      return {
        data: normalizeInvoice(result.data?.data),
        error: null,
      };
    } catch (err) {
      return {
        data: null,
        error: err.message || "Failed to create invoice",
      };
    }
  },

  // Update invoice
  updateInvoice: async (id, payload) => {
    try {
      const normalizedPayload = {
        ...payload,
      };

      if ("status" in normalizedPayload) {
        normalizedPayload.status = normalizeInvoiceStatus(normalizedPayload.status);
      }

      const result = await http.patch(
        ENDPOINTS.INVOICES.UPDATE(id),
        normalizedPayload
      );

      if (result.error) {
        return {
          data: null,
          error: result.error,
          errorData: result.errorData,
        };
      }

      return {
        data: normalizeInvoice(result.data?.data),
        error: null,
      };
    } catch (err) {
      return {
        data: null,
        error: err.message || "Failed to update invoice",
      };
    }
  },

  // Delete invoice
  deleteInvoice: async (id) => {
    try {
      const result = await http.delete(ENDPOINTS.INVOICES.DELETE(id));

      if (result.error) {
        return { data: null, error: result.error };
      }

      return { data: true, error: null };
    } catch (err) {
      return {
        data: null,
        error: err.message || "Failed to delete invoice",
      };
    }
  },
};

export default invoicesService;