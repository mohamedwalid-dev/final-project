// ─── services/invoicesService.js ──────────────────────────────────────────────
// ✅ Consistent with financeService.js pattern ({ data, error } contract)
// ✅ AbortController support
// ✅ Normalized error handling
// ✅ Mock data included — swap each mock body with real axios/fetch calls
//
// HOW TO CONNECT TO BACKEND:
//   1. Install axios: npm install axios
//   2. Replace each mock body (marked with // 🔌 SWAP) with real API call
//   3. Pass `signal` to axios: axios.get(url, { signal })
//   4. Example:
//      fetchInvoices: (filters, signal) => fetchSafe(async () => {
//        const { data } = await axios.get("/api/invoices", { params: filters, signal });
//        return data;
//      }),

// ── Mock Data ─────────────────────────────────────────────────────────────────
const _INVOICES = [
  { id: "INV-8429", customer: "Acme Dynamics",         corpId: "CORP ID: 8429", status: "Paid",    created: "2023-10-24", due: "2023-11-08", amount: 12450.00  },
  { id: "INV-8430", customer: "Global Tech Solutions",  corpId: "CORP ID: 8430", status: "Pending", created: "2023-10-25", due: "2023-11-10", amount: 3200.50   },
  { id: "INV-8431", customer: "Nebula Creative",        corpId: "CORP ID: 8431", status: "Overdue", created: "2023-10-22", due: "2023-10-29", amount: 890.00    },
  { id: "INV-8432", customer: "Riverbed Logistics",     corpId: "CORP ID: 8432", status: "Draft",   created: "2023-10-23", due: "2023-11-10", amount: 4560.75   },
  { id: "INV-8433", customer: "Starlight Industries",   corpId: "CORP ID: 8433", status: "Paid",    created: "2023-10-25", due: "2023-11-09", amount: 15700.00  },
  { id: "INV-8434", customer: "Apex Dynamics",          corpId: "CORP ID: 8434", status: "Overdue", created: "2023-10-18", due: "2023-10-20", amount: 5600.00   },
  { id: "INV-8435", customer: "NovaBridge Inc",         corpId: "CORP ID: 8435", status: "Paid",    created: "2023-10-17", due: "2023-10-31", amount: 22300.00  },
  { id: "INV-8436", customer: "Lumina Digital",         corpId: "CORP ID: 8436", status: "Pending", created: "2023-10-16", due: "2023-10-30", amount: 8100.00   },
  { id: "INV-8437", customer: "SkyNet Solutions",       corpId: "CORP ID: 8437", status: "Pending", created: "2023-10-19", due: "2023-11-02", amount: 9750.00   },
  { id: "INV-8438", customer: "Pioneer Tech",           corpId: "CORP ID: 8438", status: "Paid",    created: "2023-10-20", due: "2023-11-03", amount: 18900.00  },
  { id: "INV-8439", customer: "Zenith Corp",            corpId: "CORP ID: 8439", status: "Draft",   created: "2023-10-21", due: "2023-11-04", amount: 3300.25   },
  { id: "INV-8440", customer: "Cascade Systems",        corpId: "CORP ID: 8440", status: "Overdue", created: "2023-10-10", due: "2023-10-15", amount: 7420.00   },
  { id: "INV-8441", customer: "Momentum Analytics",     corpId: "CORP ID: 8441", status: "Paid",    created: "2023-10-12", due: "2023-10-26", amount: 11500.00  },
  { id: "INV-8442", customer: "Redstone Ventures",      corpId: "CORP ID: 8442", status: "Pending", created: "2023-10-14", due: "2023-10-28", amount: 6780.00   },
  { id: "INV-8443", customer: "Vertex Data Labs",       corpId: "CORP ID: 8443", status: "Paid",    created: "2023-10-15", due: "2023-10-29", amount: 29400.00  },
];

const _STATS = {
  totalInvoiced: 248500.00,
  outstanding:    45210.50,
  received:      192840.00,
  overdue:        10450.00,
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const normalizeError = (err) => {
  if (err?.name === "AbortError") return null;        // silently swallow cancel
  if (err instanceof Error)       return err.message;
  if (typeof err === "string")    return err;
  return "An unexpected error occurred";
};

async function fetchSafe(fn) {
  try {
    const data = await fn();
    return { data, error: null };
  } catch (err) {
    const error = normalizeError(err);
    if (!error) return { data: null, error: null };   // aborted request
    return { data: null, error };
  }
}

// ── Service API ───────────────────────────────────────────────────────────────
const invoicesService = {

  /**
   * Fetch paginated / filtered invoices list.
   *
   * @param {Object} filters - { from: "YYYY-MM-DD", to: "YYYY-MM-DD", status: string, q: string }
   * @param {AbortSignal} signal
   * @returns {{ data: Invoice[], error: string|null }}
   *
   * 🔌 SWAP mock with:
   *   const { data } = await axios.get("/api/invoices", { params: filters, signal });
   *   return data;
   */
  fetchInvoices: (filters = {}, signal) =>
    fetchSafe(async () => {
      await delay(300);                               // simulate network
      return _INVOICES;
    }),

  /**
   * Fetch invoice stats / KPIs for the summary cards.
   *
   * @returns {{ data: InvoiceStats, error: string|null }}
   *
   * 🔌 SWAP mock with:
   *   const { data } = await axios.get("/api/invoices/stats");
   *   return data;
   */
  fetchInvoiceStats: (signal) =>
    fetchSafe(async () => {
      await delay(150);
      return _STATS;
    }),

  /**
   * Fetch a single invoice by ID.
   *
   * @param {string} id
   * @returns {{ data: Invoice, error: string|null }}
   *
   * 🔌 SWAP mock with:
   *   const { data } = await axios.get(`/api/invoices/${id}`);
   *   return data;
   */
  fetchInvoiceById: (id, signal) =>
    fetchSafe(async () => {
      await delay(200);
      const inv = _INVOICES.find((i) => i.id === id);
      if (!inv) throw new Error(`Invoice ${id} not found`);
      return inv;
    }),

  /**
   * Create a new invoice.
   *
   * @param {Object} payload - { form, lineItems, summary }
   * @returns {{ data: Invoice, error: string|null }}
   *
   * 🔌 SWAP mock with:
   *   const { data } = await axios.post("/api/invoices", payload);
   *   return data;
   */
  createInvoice: (payload) =>
    fetchSafe(async () => {
      await delay(800);
      const newInvoice = {
        id:       `INV-${Date.now().toString().slice(-4)}`,
        customer: payload.form.customerName,
        corpId:   `CORP ID: ${Date.now().toString().slice(-4)}`,
        status:   "Draft",
        created:  payload.form.issueDate,
        due:      payload.form.dueDate,
        amount:   payload.summary.grandTotal,
      };
      return newInvoice;
    }),

  /**
   * Update invoice status.
   *
   * @param {string} id
   * @param {string} status - "Paid" | "Pending" | "Overdue" | "Draft"
   * @returns {{ data: Invoice, error: string|null }}
   *
   * 🔌 SWAP mock with:
   *   const { data } = await axios.patch(`/api/invoices/${id}/status`, { status });
   *   return data;
   */
  updateInvoiceStatus: (id, status) =>
    fetchSafe(async () => {
      await delay(200);
      return { id, status };
    }),

  /**
   * Delete an invoice.
   *
   * @param {string} id
   * @returns {{ data: { success: boolean }, error: string|null }}
   *
   * 🔌 SWAP mock with:
   *   await axios.delete(`/api/invoices/${id}`);
   *   return { success: true };
   */
  deleteInvoice: (id) =>
    fetchSafe(async () => {
      await delay(300);
      return { success: true };
    }),

  /**
   * Bulk delete invoices.
   *
   * @param {string[]} ids
   * @returns {{ data: { deleted: number }, error: string|null }}
   *
   * 🔌 SWAP mock with:
   *   const { data } = await axios.post("/api/invoices/bulk-delete", { ids });
   *   return data;
   */
  bulkDeleteInvoices: (ids) =>
    fetchSafe(async () => {
      await delay(400);
      return { deleted: ids.length };
    }),
};

export default invoicesService;