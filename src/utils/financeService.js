// ─── utils/financeService.js ──────────────────────────────────────────────────
// Service layer — swap mock bodies with axios calls when connecting to backend
// ✅ Normalized error handling
// ✅ AbortController support (pass signal to real fetch calls)
// ✅ Consistent { data, error } contract

// ── Mock Data ─────────────────────────────────────────────────────────────────
const _CASH_FLOW = [
  { month: "Jan", revenue: 38000, expenses: 28000 },
  { month: "Feb", revenue: 42000, expenses: 31000 },
  { month: "Mar", revenue: 45000, expenses: 33000 },
  { month: "Apr", revenue: 41000, expenses: 30000 },
  { month: "May", revenue: 55000, expenses: 35000 },
  { month: "Jun", revenue: 62000, expenses: 38000 },
];

const _EXPENSES = [
  { name: "Payroll",    value: 45, color: "#3B5BDB" },
  { name: "Marketing",  value: 20, color: "#4DABF7" },
  { name: "Operations", value: 15, color: "#38D9A9" },
  { name: "Technology", value: 12, color: "#845EF7" },
  { name: "Others",     value: 8,  color: "#F59F00" },
];

const _INVOICES = [
  { id: "INV-8842", customer: "Acme Corp",             corpId: "CORP ID: 8842", status: "Paid",    created: "2024-05-10", due: "2024-05-24", amount: 12500.00 },
  { id: "INV-8843", customer: "Global Tech Solutions",  corpId: "CORP ID: 8843", status: "Pending", created: "2024-05-12", due: "2024-05-28", amount: 8400.50  },
  { id: "INV-8844", customer: "Horizon Ventures",       corpId: "CORP ID: 8844", status: "Overdue", created: "2024-05-14", due: "2024-05-18", amount: 3200.00  },
  { id: "INV-8845", customer: "Stellar Logistics",      corpId: "CORP ID: 8845", status: "Paid",    created: "2024-05-15", due: "2024-05-29", amount: 15750.00 },
  { id: "INV-8846", customer: "Lumina Digital",         corpId: "CORP ID: 8846", status: "Pending", created: "2024-05-16", due: "2024-05-30", amount: 8100.00  },
  { id: "INV-8847", customer: "NovaBridge Inc",         corpId: "CORP ID: 8847", status: "Paid",    created: "2024-05-17", due: "2024-05-31", amount: 22300.00 },
  { id: "INV-8848", customer: "Apex Dynamics",          corpId: "CORP ID: 8848", status: "Overdue", created: "2024-05-18", due: "2024-05-20", amount: 5600.00  },
  { id: "INV-8849", customer: "SkyNet Solutions",       corpId: "CORP ID: 8849", status: "Pending", created: "2024-05-19", due: "2024-06-02", amount: 9750.00  },
];

const _STAT_CARDS = [
  { id: "revenue",  label: "Total Revenue",        value: "$1,482,900", change: "+12.5%", changeType: "up"      },
  { id: "profit",   label: "Net Profit",           value: "$452,000",   change: "+8.2%",  changeType: "up"      },
  { id: "expenses", label: "Operational Expenses", value: "$920,400",   change: "+14.1%", changeType: "down"    },
  { id: "unpaid",   label: "Unpaid Invoices",      value: "$124,500",   change: "-2.4%",  changeType: "neutral" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const normalizeError = (err) => {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "An unexpected error occurred";
};

async function fetchSafe(fn) {
  try {
    const data = await fn();
    return { data, error: null };
  } catch (err) {
    return { data: null, error: normalizeError(err) };
  }
}

// ── Service API ───────────────────────────────────────────────────────────────
// Replace each mock body with: () => axios.get("/api/...").then(r => r.data)
// Pass `signal` to axios for AbortController support: axios.get(url, { signal })

const financeService = {
  fetchStatCards:        (signal) => fetchSafe(async () => { await delay(150); return _STAT_CARDS;  }),
  fetchCashFlow:         (signal) => fetchSafe(async () => { await delay(200); return _CASH_FLOW;   }),
  fetchExpenseBreakdown: (signal) => fetchSafe(async () => { await delay(200); return _EXPENSES;    }),
  fetchInvoices:         (signal) => fetchSafe(async () => { await delay(300); return _INVOICES;    }),
};

export default financeService; 