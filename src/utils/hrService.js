// ─── utils/hrService.js ───────────────────────────────────────────────────────
// ✅ Consistent { data, error } contract — same pattern as financeService.js
// ✅ Swap mock bodies with real axios calls when connecting to backend
// 🔌 SWAP guide: replace each mock body with axios.get("/api/...", { signal })

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const normalizeError = (err) => {
  if (err?.name === "AbortError") return null;
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
    if (!error) return { data: null, error: null };
    return { data: null, error };
  }
}

// ── Mock Data ─────────────────────────────────────────────────────────────────

const _STAT_CARDS = [
  { id: "workforce",   icon: "👥", label: "Total Workforce",     value: "1,248", change: "+12% YoY",  changeType: "up"      },
  { id: "leave",       icon: "📅", label: "On Leave Today",      value: "24",    change: "-2% vs LW", changeType: "neutral" },
  { id: "recruiting",  icon: "📈", label: "Active Recruitments", value: "18",    change: "+4 New",    changeType: "up"      },
  { id: "retention",   icon: "🔄", label: "Retention Rate",      value: "94.2%", change: "+0.6%",     changeType: "up"      },
];

const _EMPLOYEES = [
  { id: 1,  name: "Sarah Jenkins",    title: "Sr. Product Designer",   dept: "Design",      location: "New York",    status: "active",  avatar: "SJ", color: "#3B5BDB" },
  { id: 2,  name: "Marcus Thompson",  title: "Fullstack Engineer",     dept: "Engineering", location: "London",      status: "active",  avatar: "MT", color: "#F59F00" },
  { id: 3,  name: "Elena Rodriguez",  title: "HR Manager",             dept: "HR",          location: "Madrid",      status: "active",  avatar: "ER", color: "#2F9E44" },
  { id: 4,  name: "David Chen",       title: "Financial Analyst",      dept: "Finance",     location: "Singapore",   status: "leave",   avatar: "DC", color: "#845EF7" },
  { id: 5,  name: "Sophie Alistair",  title: "Marketing Specialist",   dept: "Marketing",   location: "New York",    status: "active",  avatar: "SA", color: "#2F9E44" },
  { id: 6,  name: "Julian Voss",      title: "DevOps Engineer",        dept: "Engineering", location: "Berlin",      status: "inactive",avatar: "JV", color: "#FA5252" },
  { id: 7,  name: "Aisha Patel",      title: "UX Researcher",          dept: "Design",      location: "Toronto",     status: "active",  avatar: "AP", color: "#3B5BDB" },
  { id: 8,  name: "Leo Martinez",     title: "Backend Engineer",       dept: "Engineering", location: "Mexico City", status: "active",  avatar: "LM", color: "#F59F00" },
  { id: 9,  name: "Natalie Brooks",   title: "Product Manager",        dept: "Product",     location: "San Francisco",status: "active", avatar: "NB", color: "#4DABF7" },
  { id: 10, name: "Kai Nakamura",     title: "Data Scientist",         dept: "Engineering", location: "Tokyo",       status: "active",  avatar: "KN", color: "#2F9E44" },
  { id: 11, name: "Zara Williams",    title: "Sales Executive",        dept: "Sales",       location: "Dubai",       status: "active",  avatar: "ZW", color: "#845EF7" },
  { id: 12, name: "Omar Hassan",      title: "Support Specialist",     dept: "Support",     location: "Cairo",       status: "active",  avatar: "OH", color: "#F59F00" },
];

const _LEAVE_REQUESTS = [
  { id: 1, name: "Marcus Thorne",  avatar: "MT", color: "#F59F00", type: "Sick Leave",   days: 2, from: "Oct 24", to: "Oct 25" },
  { id: 2, name: "David Chen",     avatar: "DC", color: "#845EF7", type: "Vacation",     days: 5, from: "Nov 01", to: "Nov 05" },
  { id: 3, name: "Sophie Alistair",avatar: "SA", color: "#2F9E44", type: "Personal Day", days: 1, from: "Nov 08", to: "Nov 08" },
];

const _TEAM_CAPACITY = [
  { dept: "Engineering", pct: 85, color: "#3B5BDB" },
  { dept: "Design",      pct: 80, color: "#845EF7" },
  { dept: "Sales",       pct: 75, color: "#2F9E44" },
  { dept: "Product",     pct: 70, color: "#F59F00" },
];

const _DEPARTMENTS = ["All Departments", "Engineering", "Design", "Marketing", "Finance", "HR", "Sales", "Support", "Product"];

// ── Service ───────────────────────────────────────────────────────────────────
const hrService = {
  // 🔌 SWAP: axios.get("/api/hr/stats", { signal })
  fetchStatCards:    (signal) => fetchSafe(async () => { await delay(150); return _STAT_CARDS;    }),
  // 🔌 SWAP: axios.get("/api/hr/employees", { params: filters, signal })
  fetchEmployees:    (filters, signal) => fetchSafe(async () => { await delay(300); return _EMPLOYEES; }),
  // 🔌 SWAP: axios.get("/api/hr/leave-requests", { signal })
  fetchLeaveRequests:(signal) => fetchSafe(async () => { await delay(200); return _LEAVE_REQUESTS; }),
  // 🔌 SWAP: axios.get("/api/hr/team-capacity", { signal })
  fetchTeamCapacity: (signal) => fetchSafe(async () => { await delay(250); return _TEAM_CAPACITY;  }),
  // 🔌 SWAP: axios.get("/api/hr/departments", { signal })
  fetchDepartments:  (signal) => fetchSafe(async () => { await delay(100); return _DEPARTMENTS;    }),
  // 🔌 SWAP: axios.patch(`/api/hr/leave-requests/${id}`, { action })
  respondToLeave:    (id, action) => fetchSafe(async () => { await delay(400); return { id, action, success: true }; }),
  // 🔌 SWAP: axios.post("/api/hr/employees", payload)
  addEmployee:       (payload) => fetchSafe(async () => { await delay(600); return { ...payload, id: Date.now() }; }),
};

export default hrService;