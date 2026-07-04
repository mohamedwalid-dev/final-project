// ─── Pages/DashboardPage.jsx ──────────────────────────────────────────────────

import { useState, useEffect, useCallback, useRef, memo } from "react";
import { useNavigate } from "react-router-dom";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Banknote,
  Boxes,
  CalendarDays,
  CheckCircle2,
  CircleDollarSign,
  ClipboardList,
  Download,
  Handshake,
  Headphones,
  Plus,
  ReceiptText,
  Settings,
  ShoppingCart,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";
import shell from "../styles/AppShell.module.css";

// ─────────────────────────────────────────────────────────────────────────────
// BACKEND SERVICE STUB (swap with real API calls)
// ─────────────────────────────────────────────────────────────────────────────
const dashboardService = {
  async fetchStats(range = "monthly", signal) {
    await new Promise(r => setTimeout(r, 700));
    const multiplier = range === "weekly" ? 0.25 : range === "yearly" ? 12 : 1;
    return {
      data: [
        { id: "revenue",   label: "Total Revenue",  value: Math.round(2482900 * multiplier), raw: 2482900 * multiplier, change: "+12.5%", changeType: "up"   },
        { id: "expenses",  label: "Total Expenses", value: Math.round(1102450 * multiplier), raw: 1102450 * multiplier, change: "+4.2%",  changeType: "down" },
        { id: "profit",    label: "Net Profit",     value: Math.round(1380450 * multiplier), raw: 1380450 * multiplier, change: "+18.1%", changeType: "up"   },
        { id: "orders",    label: "Sales Orders",   value: Math.round(1240  * multiplier),   raw: 1240  * multiplier,   change: "+8.4%",  changeType: "up"   },
        { id: "employees", label: "Employees",      value: 458,                               raw: 458,                   change: "+2.1%",  changeType: "up"   },
      ],
    };
  },

  async fetchRevenueChart(range = "monthly", signal) {
    await new Promise(r => setTimeout(r, 900));
    const months = ["Jan","Feb","Mar","Apr","May","Jun"];
    return {
      data: months.map((month, i) => ({
        month,
        Revenue: [130000, 155000, 162000, 195000, 230000, 260000][i],
        Target:  [140000, 150000, 170000, 185000, 215000, 250000][i],
      })),
    };
  },

  async fetchEfficiency(signal) {
    await new Promise(r => setTimeout(r, 600));
    return {
      data: [
        { dept: "Sales",     pct: 92 },
        { dept: "HR",        pct: 74 },
        { dept: "Finance",   pct: 81 },
        { dept: "Inventory", pct: 68 },
        { dept: "Support",   pct: 77 },
      ],
    };
  },

  async fetchRecentOperations(signal) {
    await new Promise(r => setTimeout(r, 500));
    return {
      data: [
        { id: "op1", user: "Sarah Chen",   action: "completed payroll run for July",            hoursAgo: 2,  color: "#2F9E44" },
        { id: "op2", user: "James Wilson", action: "approved 12 new sales leads",               hoursAgo: 4,  color: "#3B5BDB" },
        { id: "op3", user: "System",       action: "Inventory alert: Warehouse A low on stock", hoursAgo: 6,  color: "#F59F00", isSystem: true },
        { id: "op4", user: "Maria Garcia", action: "scheduled team-building for HR",            hoursAgo: 24, color: "#845EF7" },
      ],
    };
  },

  async fetchTasks(signal) {
    await new Promise(r => setTimeout(r, 400));
    return {
      data: [
        { id: "t1", title: "Approve Q3 Budget Report",       priority: "High",   dueLabel: "Today",     checked: false },
        { id: "t2", title: "Annual Performance Reviews",      priority: "Medium", dueLabel: "In 2 days", checked: false },
        { id: "t3", title: "Inventory Reorder Strategy",      priority: "High",   dueLabel: "Tomorrow",  checked: false },
        { id: "t4", title: "New Customer Success Lead Intro", priority: "Low",    dueLabel: "Friday",    checked: false },
      ],
    };
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// DESIGN TOKENS
// ─────────────────────────────────────────────────────────────────────────────
const T = {
  primary:      "#3B5BDB",
  primaryLight: "#EEF2FF",
  success:      "#2F9E44",
  successLight: "#EBFBEE",
  warning:      "#F59F00",
  danger:       "#C92A2A",
  dangerLight:  "#FFF5F5",
  text:         "#1A1A2E",
  textSec:      "#495057",
  textMuted:    "#868E96",
  border:       "#E9ECEF",
  borderSoft:   "#F1F3F5",
  bg:           "#F8F9FC",
  surface:      "#ffffff",
};

const PRIORITY_META = {
  High:   { bg: "#FFEBE8", color: "#C92A2A", label: "High"   },
  Medium: { bg: "#FFF9DB", color: "#F59F00", label: "Medium" },
  Low:    { bg: "#EBFBEE", color: "#2F9E44", label: "Low"    },
};

const STAT_ICONS = {
  revenue: CircleDollarSign,
  expenses: Banknote,
  profit: TrendingUp,
  orders: ShoppingCart,
  employees: Users,
};

const CHANGE_ICONS = {
  up: ArrowUpRight,
  down: ArrowDownRight,
  neutral: ArrowRight,
};

const OPERATION_ICONS = {
  op1: CheckCircle2,
  op2: Handshake,
  op3: AlertTriangle,
  op4: CalendarDays,
};

// ─────────────────────────────────────────────────────────────────────────────
// FORMATTERS
// ─────────────────────────────────────────────────────────────────────────────
const fmtCurrency = (n) =>
  n >= 1_000_000
    ? `EGP ${(n / 1_000_000).toFixed(2)}M`.replace(".00M", "M")
    : n >= 1_000
    ? `EGP ${(n / 1_000).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`
    : `EGP ${n}`;

const fmtNumber = (n) =>
  n >= 1_000 ? `${(n / 1_000).toFixed(1)}k` : `${n}`;

const fmtValue = (stat) => {
  if (stat.id === "employees" || stat.id === "orders") return fmtNumber(stat.value);
  return fmtCurrency(stat.value);
};

// ─────────────────────────────────────────────────────────────────────────────
// ANIMATION HOOK
// ─────────────────────────────────────────────────────────────────────────────
function useAnimateIn(delay = 0) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);
  return {
    ref,
    style: {
      opacity:    visible ? 1 : 0,
      transform:  visible ? "translateY(0)" : "translateY(14px)",
      transition: `opacity 0.45s ease ${delay}ms, transform 0.45s ease ${delay}ms`,
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// ANIMATED COUNTER
// ─────────────────────────────────────────────────────────────────────────────
function AnimatedCounter({ target, format }) {
  const [display, setDisplay] = useState("0");
  const frameRef = useRef(null);

  useEffect(() => {
    if (!target && target !== 0) return;
    const duration = 900;
    const start    = performance.now();
    const tick = (now) => {
      const elapsed  = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease     = 1 - Math.pow(1 - progress, 3);
      const current  = Math.round(target * ease);
      setDisplay(format ? format(current) : current.toLocaleString());
      if (progress < 1) frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, format]);

  return <>{display}</>;
}

// ─────────────────────────────────────────────────────────────────────────────
// SKELETON
// ─────────────────────────────────────────────────────────────────────────────
const Skeleton = ({ w = "100%", h = 14, style = {} }) => (
  <div style={{
    width: w, height: h, borderRadius: 6,
    background: "linear-gradient(90deg, #F0F0F0 25%, #E0E0E0 50%, #F0F0F0 75%)",
    backgroundSize: "200% 100%",
    animation: "shimmer 1.4s infinite",
    ...style,
  }} />
);

// ─────────────────────────────────────────────────────────────────────────────
// STAT CARD
// ─────────────────────────────────────────────────────────────────────────────
const cardStyle = {
  background:    T.surface,
  border:        `1px solid ${T.border}`,
  borderRadius:  14,
  padding:       "18px 20px",
  boxShadow:     "0 1px 4px rgba(0,0,0,.04)",
  display:       "flex",
  flexDirection: "column",
};

const StatCard = memo(({ stat, loading, delay = 0 }) => {
  const anim = useAnimateIn(delay);

  const changeColor = stat?.changeType === "up"   ? T.success :
                      stat?.changeType === "down"  ? T.danger  : T.textMuted;
  const changeBg    = stat?.changeType === "up"   ? T.successLight :
                      stat?.changeType === "down"  ? T.dangerLight  : T.borderSoft;
  const Icon = stat ? (STAT_ICONS[stat.id] || Activity) : Activity;
  const ChangeIcon = stat ? (CHANGE_ICONS[stat.changeType] || CHANGE_ICONS.neutral) : CHANGE_ICONS.neutral;
  const isFeatured = stat?.id === "revenue";

  if (loading) return (
    <div style={{ ...cardStyle, ...anim.style }}>
      <Skeleton w={42} h={42} style={{ borderRadius: "50%", marginBottom: 10 }} />
      <Skeleton w="60%" h={12} style={{ marginBottom: 6 }} />
      <Skeleton w="80%" h={22} style={{ marginBottom: 6 }} />
      <Skeleton w="40%" h={12} />
    </div>
  );

  return (
    <article ref={anim.ref} style={{ ...cardStyle, ...anim.style }} aria-label={stat.label}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
        <div
          style={{
            width: 42,
            height: 42,
            borderRadius: "50%",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            background: isFeatured ? T.primary : "#F8F9FA",
            border: `1px solid ${isFeatured ? T.primary : T.border}`,
            color: isFeatured ? "#fff" : T.primary,
          }}
          aria-hidden="true"
        >
          <Icon size={19} strokeWidth={2.2} />
        </div>
        <p style={{ fontSize: 12, color: T.textMuted, margin: 0, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.4px" }}>
          {stat.label}
        </p>
      </div>
      <p style={{ fontSize: 22, fontWeight: 800, color: T.text, margin: "0 0 6px", letterSpacing: "-0.5px", lineHeight: 1 }}>
        <AnimatedCounter target={stat.raw} format={(n) => fmtValue({ ...stat, value: n })} />
      </p>
      <span style={{
        display: "inline-flex", alignItems: "center", gap: 4,
        padding: "2px 8px", borderRadius: 20,
        fontSize: 11.5, fontWeight: 700,
        background: changeBg, color: changeColor,
        width: "fit-content",
      }}>
        <ChangeIcon size={13} aria-hidden="true" />
        {stat.change}
      </span>
    </article>
  );
});
StatCard.displayName = "StatCard";

// ─────────────────────────────────────────────────────────────────────────────
// REVENUE CHART
// ─────────────────────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: 10, padding: "10px 14px", boxShadow: "0 4px 16px rgba(0,0,0,.1)",
    }}>
      <p style={{ fontSize: 12, fontWeight: 700, color: T.textMuted, margin: "0 0 6px" }}>{label}</p>
      {payload.map(e => (
        <p key={e.name} style={{ fontSize: 13, fontWeight: 700, color: e.color, margin: "2px 0" }}>
          {e.name}: <span style={{ color: T.text }}>EGP {(e.value / 1000).toFixed(0)}k</span>
        </p>
      ))}
    </div>
  );
};

const RevenueChart = memo(({ data, loading, range, onRangeChange }) => {
  const anim   = useAnimateIn(200);
  const RANGES = ["weekly", "monthly", "yearly"];

  return (
    <div ref={anim.ref} style={{ ...cardStyle, flex: 1, minWidth: 0, ...anim.style }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: T.text, margin: 0 }}>Revenue Growth Trend</h3>
          <p style={{ fontSize: 12, color: T.textMuted, margin: "3px 0 0" }}>
            Comparison between actual revenue and set monthly targets.
          </p>
        </div>
        <div style={{ display: "flex", background: T.borderSoft, borderRadius: 8, padding: 3, gap: 2 }}>
          {RANGES.map(r => (
            <button key={r} onClick={() => onRangeChange(r)} style={{
              padding: "5px 12px", border: "none", borderRadius: 6,
              fontSize: 12, fontWeight: 600, cursor: "pointer",
              background: range === r ? T.surface : "transparent",
              color:      range === r ? T.primary : T.textMuted,
              boxShadow:  range === r ? "0 1px 3px rgba(0,0,0,.1)" : "none",
              transition: "all 0.15s", textTransform: "capitalize",
            }}>
              {r}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 12 }}>
        {[{ label: "Revenue", color: "#3B5BDB" }, { label: "Target", color: "#CED4DA" }].map(l => (
          <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: T.textMuted }}>
            <div style={{ width: 10, height: 10, borderRadius: 50, background: l.color }} />
            {l.label}
          </div>
        ))}
      </div>

      {loading ? (
        <div style={{ height: 220, display: "flex", alignItems: "flex-end", gap: 8 }}>
          {[60, 80, 55, 90, 75, 95].map((h, i) => (
            <Skeleton key={i} w="100%" h={h * 2} style={{ flex: 1, borderRadius: "4px 4px 0 0" }} />
          ))}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="gradRevenue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#3B5BDB" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#3B5BDB" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradTarget" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#CED4DA" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#CED4DA" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={T.borderSoft} />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: T.textMuted }} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fontSize: 11, fill: T.textMuted }}
              axisLine={false} tickLine={false}
              tickFormatter={v => `EGP ${v / 1000}k`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="Revenue" stroke="#3B5BDB" strokeWidth={2.5} fill="url(#gradRevenue)" dot={false} />
            <Area type="monotone" dataKey="Target"  stroke="#CED4DA" strokeWidth={2}   fill="url(#gradTarget)"  dot={false} strokeDasharray="4 4" />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
});
RevenueChart.displayName = "RevenueChart";

// ─────────────────────────────────────────────────────────────────────────────
// AI BUSINESS INSIGHTS PANEL
// ─────────────────────────────────────────────────────────────────────────────
const AI_INSIGHTS = [
  "Operating expenses rose 4% due to cloud scaling costs.",
  "North America conversion rates are at an all-time high (4.2%).",
  "Inventory turnover for SKU-402 is slower than industry average.",
];

const AIInsightsPanel = memo(() => {
  const anim  = useAnimateIn(300);
  const [pulse, setPulse] = useState(true);

  useEffect(() => {
    const id = setInterval(() => setPulse(p => !p), 1200);
    return () => clearInterval(id);
  }, []);

  return (
    <div ref={anim.ref} style={{ ...cardStyle, width: 240, flexShrink: 0, ...anim.style }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <div style={{
          width: 34, height: 34, borderRadius: "50%",
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          background: "#F8F9FA", border: `1px solid ${T.border}`, color: T.primary,
          flexShrink: 0,
        }} aria-hidden="true">
          <Sparkles size={16} strokeWidth={2.2} />
        </div>
        <p style={{ fontSize: 13, fontWeight: 700, color: T.text, margin: 0, flex: 1 }}>Finance Agent Decision</p>
        <span style={{
          Display: "flex", alignItems: "center", gap: 4,
          fontSize: 10, fontWeight: 700, color: T.success,
          backgrounD: T.successLight, padding: "2px 7px", borderRadius: 20,
        }}>
          <span style={{
            width: 5, height: 5, borderRadius: "50%", background: T.success,
            opacity: pulse ? 1 : 0.3, transition: "opacity 0.4s",
          }} />
          Live
        </span>
      </div>

      <div style={{ background: T.borderSoft, borderRadius: 10, padding: "12px 14px", marginBottom: 14 }}>
        <p style={{ fontSize: 12.5, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>Revenue Outlook</p>
        <p style={{ fontSize: 12, color: T.textSec, margin: 0, lineHeight: 1.6 }}>
          Current trajectory suggests a 12% beat on Q3 targets if Sales velocity maintains through August.
        </p>
      </div>

      <p style={{ fontSize: 10.5, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.6px", margin: "0 0 8px" }}>
        Critical Observations
      </p>
      <ul style={{ margin: 0, paddingLeft: 16, display: "flex", flexDirection: "column", gap: 7 }}>
        {AI_INSIGHTS.map((insight, i) => (
          <li key={i} style={{ fontSize: 12, color: T.textSec, lineHeight: 1.5 }}>{insight}</li>
        ))}
      </ul>

      <button
        style={{
          marginTop: 16, width: "100%", padding: "11px 0",
          background: T.primary, color: "#fff",
          border: "none", borderRadius: 10,
          fontSize: 13, fontWeight: 700, cursor: "pointer",
          transition: "opacity 0.15s",
        }}
        onMouseEnter={e => e.currentTarget.style.opacity = "0.88"}
        onMouseLeave={e => e.currentTarget.style.opacity = "1"}
      >
        Deep Finance decision
      </button>
    </div>
  );
});
AIInsightsPanel.displayName = "AIInsightsPanel";

// ─────────────────────────────────────────────────────────────────────────────
// EFFICIENCY BY DEPARTMENT
// ─────────────────────────────────────────────────────────────────────────────
const EfficiencyChart = memo(({ data, loading }) => {
  const anim  = useAnimateIn(400);
  const [drawn, setDrawn] = useState(false);

  useEffect(() => {
    if (!loading && data?.length) {
      const t = setTimeout(() => setDrawn(true), 100);
      return () => clearTimeout(t);
    }
  }, [loading, data]);

  return (
    <div ref={anim.ref} style={{ ...anim.style }}>
      <h3 style={{ fontSize: 14.5, fontWeight: 700, color: T.text, margin: "0 0 4px" }}>Efficiency by Department</h3>
      <p style={{ fontSize: 12, color: T.textMuted, margin: "0 0 14px" }}>Performance index scoring across core modules</p>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[1,2,3,4,5].map((_, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Skeleton w={60} h={12} />
              <Skeleton w="100%" h={10} style={{ flex: 1 }} />
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {data.map(item => (
            <div key={item.dept} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 12, color: T.textSec, width: 64, textAlign: "right", flexShrink: 0 }}>
                {item.dept}
              </span>
              <div style={{ flex: 1, height: 12, background: T.borderSoft, borderRadius: 99, overflow: "hidden" }}>
                <div style={{
                  height: "100%", borderRadius: 99, background: T.primary,
                  width: drawn ? `${item.pct}%` : "0%",
                  transition: "width 0.9s cubic-bezier(0.22,1,0.36,1)",
                }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});
EfficiencyChart.displayName = "EfficiencyChart";

// ─────────────────────────────────────────────────────────────────────────────
// RECENT OPERATIONS
// ─────────────────────────────────────────────────────────────────────────────
const RecentOperations = memo(({ ops, loading }) => {
  const anim = useAnimateIn(450);

  return (
    <div ref={anim.ref} style={{ ...anim.style }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <h3 style={{ fontSize: 14.5, fontWeight: 700, color: T.text, margin: 0 }}>Recent Operations</h3>
          <p style={{ fontSize: 12, color: T.textMuted, margin: "2px 0 0" }}>Live feed of enterprise-wide actions</p>
        </div>
        <button style={{
          background: "none", border: "none", fontSize: 12, fontWeight: 600,
          color: T.primary, cursor: "pointer", padding: "4px 8px",
          display: "inline-flex", alignItems: "center", gap: 5,
        }}>
          <ClipboardList size={14} aria-hidden="true" />
          View Log
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <Skeleton w={32} h={32} style={{ borderRadius: 8, flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <Skeleton w="80%" h={12} style={{ marginBottom: 5 }} />
                <Skeleton w="40%" h={10} />
              </div>
            </div>
          ))
        ) : ops.map(op => {
          const OperationIcon = OPERATION_ICONS[op.id] || Activity;
          return (
          <div key={op.id} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{
              width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
              background: `${op.color}18`,
              color: op.color,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              border: `1px solid ${op.color}22`,
            }} aria-hidden="true">
              <OperationIcon size={15} strokeWidth={2.2} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontSize: 12.5, color: T.text, margin: 0, lineHeight: 1.5 }}>
                {!op.isSystem && <strong>{op.user} </strong>}
                {op.isSystem  && <strong style={{ color: T.warning }}>System </strong>}
                {op.action}
              </p>
              <p style={{ fontSize: 11, color: T.textMuted, margin: "2px 0 0" }}>
                {op.hoursAgo < 24 ? `${op.hoursAgo} hours ago` : "1 day ago"}
              </p>
            </div>
          </div>
        )})}
      </div>
    </div>
  );
});
RecentOperations.displayName = "RecentOperations";

// ─────────────────────────────────────────────────────────────────────────────
// EXECUTIVE TASKS
// ─────────────────────────────────────────────────────────────────────────────
const ExecutiveTasks = memo(({ tasks: initialTasks, loading }) => {
  const anim  = useAnimateIn(500);
  const [tasks, setTasks] = useState([]);

  useEffect(() => { setTasks(initialTasks || []); }, [initialTasks]);

  const toggle = (id) =>
    setTasks(prev => prev.map(t => t.id === id ? { ...t, checked: !t.checked } : t));

  return (
    <div ref={anim.ref} style={{ ...cardStyle, ...anim.style }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h3 style={{ fontSize: 14.5, fontWeight: 700, color: T.text, margin: 0 }}>Executive Tasks</h3>
        <button style={{
          width: 28, height: 28, borderRadius: 7,
          border: `1px solid ${T.border}`, background: T.surface,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
          color: T.textMuted,
        }} aria-label="Add executive task">
          <Plus size={15} aria-hidden="true" />
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <Skeleton w={18} h={18} style={{ borderRadius: 5, flexShrink: 0 }} />
              <Skeleton w="70%" h={12} />
              <Skeleton w={50} h={20} style={{ marginLeft: "auto", borderRadius: 10 }} />
            </div>
          ))
        ) : tasks.map(task => {
          const pm = PRIORITY_META[task.priority] ?? PRIORITY_META.Low;
          return (
            <label key={task.id} style={{
              display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer",
              padding: "8px 0", borderBottom: `1px solid ${T.borderSoft}`,
            }}>
              <input
                type="checkbox"
                checked={task.checked}
                onChange={() => toggle(task.id)}
                style={{ width: 16, height: 16, accentColor: T.primary, marginTop: 1, cursor: "pointer" }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  fontSize: 13, fontWeight: 600, color: task.checked ? T.textMuted : T.text,
                  margin: 0, textDecoration: task.checked ? "line-through" : "none",
                  transition: "color 0.2s",
                }}>
                  {task.title}
                </p>
                <p style={{ fontSize: 11, color: T.textMuted, margin: "2px 0 0" }}>
                  {task.dueLabel}
                </p>
              </div>
              <span style={{
                fontSize: 10.5, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
                background: pm.bg, color: pm.color, flexShrink: 0,
              }}>
                {pm.label}
              </span>
            </label>
          );
        })}
      </div>

      <button
        style={{
          marginTop: 14, width: "100%", padding: "10px 0",
          background: T.borderSoft, color: T.textSec,
          border: `1px solid ${T.border}`, borderRadius: 10,
          fontSize: 13, fontWeight: 600, cursor: "pointer",
          transition: "background 0.15s",
        }}
        onMouseEnter={e => e.currentTarget.style.background = T.border}
        onMouseLeave={e => e.currentTarget.style.background = T.borderSoft}
      >
        Sync Calendar
      </button>
    </div>
  );
});
ExecutiveTasks.displayName = "ExecutiveTasks";

// ─────────────────────────────────────────────────────────────────────────────
// ENTERPRISE SHORTCUTS
// ─────────────────────────────────────────────────────────────────────────────
const SHORTCUTS = [
  { id: "invoice",   label: "Create Invoice",  path: "/invoices/new", icon: ReceiptText },
  { id: "employee",  label: "Employee Portal", path: "/hr",           icon: Users },
  { id: "leads",     label: "Leads Kanban",    path: "/sales",        icon: Handshake },
  { id: "inventory", label: "Inventory Audit", path: "/inventory",    icon: Boxes },
  { id: "support",   label: "Support Tickets", path: "/support",      icon: Headphones },
  { id: "settings",  label: "System Settings", path: "/settings",     icon: Settings },
];

const EnterpriseShortcuts = memo(({ navigate }) => {
  const anim = useAnimateIn(600);
  return (
    <div ref={anim.ref} style={{ ...anim.style, marginTop: 8 }}>
      <p style={{
        fontSize: 11, fontWeight: 700, color: T.textMuted,
        textTransform: "uppercase", letterSpacing: "0.7px", margin: "0 0 14px",
      }}>
        Enterprise Shortcuts
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12 }}>
        {SHORTCUTS.map(sc => {
          const ShortcutIcon = sc.icon;
          return (
          <button
            key={sc.id}
            onClick={() => navigate(sc.path)}
            style={{
              display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
              padding: "16px 8px", border: `1px solid ${T.border}`,
              borderRadius: 12, background: T.surface, cursor: "pointer",
              transition: "all 0.15s", fontSize: 12, fontWeight: 600, color: T.textSec,
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = T.primary;
              e.currentTarget.style.background  = T.primaryLight;
              e.currentTarget.style.color       = T.primary;
              e.currentTarget.style.transform   = "translateY(-2px)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = T.border;
              e.currentTarget.style.background  = T.surface;
              e.currentTarget.style.color       = T.textSec;
              e.currentTarget.style.transform   = "translateY(0)";
            }}
            aria-label={sc.label}
          >
            <div style={{
              width: 40, height: 40, borderRadius: "50%", background: "#F8F9FA",
              border: `1px solid ${T.border}`, color: T.primary,
              display: "inline-flex", alignItems: "center", justifyContent: "center",
            }} aria-hidden="true">
              <ShortcutIcon size={18} strokeWidth={2.2} />
            </div>
            <span style={{ textAlign: "center", lineHeight: 1.3 }}>{sc.label}</span>
          </button>
        )})}
      </div>
    </div>
  );
});
EnterpriseShortcuts.displayName = "EnterpriseShortcuts";

// ─────────────────────────────────────────────────────────────────────────────
// FOOTER
// ─────────────────────────────────────────────────────────────────────────────
const Footer = () => (
  <footer style={{
    borderTop: `1px solid ${T.border}`,
    padding: "14px 32px",
    display: "flex", justifyContent: "space-between", alignItems: "center",
    fontSize: 11.5, color: T.textMuted,
  }}>
    <span>2026 Prime ERP Systems. All rights reserved.</span>
    <div style={{ display: "flex", gap: 16 }}>
      {["Privacy Policy", "Terms of Service"].map(l => (
        <a key={l} href="#" style={{ color: T.textMuted, textDecoration: "none" }}
          onMouseEnter={e => e.currentTarget.style.color = T.primary}
          onMouseLeave={e => e.currentTarget.style.color = T.textMuted}
        >{l}</a>
      ))}
      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#2F9E44" }} />
        System Status: Operational
      </span>
      <span>v1-stable</span>
    </div>
  </footer>
);

// ─────────────────────────────────────────────────────────────────────────────
// GLOBAL STYLES
// ─────────────────────────────────────────────────────────────────────────────
const GlobalStyles = () => (
  <style>{`
    @keyframes shimmer {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    * { box-sizing: border-box; }
    body { margin: 0; }
  `}</style>
);

// ─────────────────────────────────────────────────────────────────────────────
// MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [activeNav,  setActiveNav]  = useState("dashboard");
  const [range,      setRange]      = useState("monthly");
  const [stats,      setStats]      = useState([]);
  const [chartData,  setChartData]  = useState([]);
  const [efficiency, setEfficiency] = useState([]);
  const [operations, setOperations] = useState([]);
  const [tasks,      setTasks]      = useState([]);

  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingChart, setLoadingChart] = useState(true);
  const [loadingEffic, setLoadingEffic] = useState(true);
  const [loadingOps,   setLoadingOps]   = useState(true);
  const [loadingTasks, setLoadingTasks] = useState(true);

  const navigate = useNavigate();

  const loadPage = useCallback((r = range) => {
    const controller = new AbortController();
    setLoadingStats(true);
    setLoadingChart(true);

    dashboardService.fetchStats(r, controller.signal).then(res => {
      setStats(res.data); setLoadingStats(false);
    });
    dashboardService.fetchRevenueChart(r, controller.signal).then(res => {
      setChartData(res.data); setLoadingChart(false);
    });
    dashboardService.fetchEfficiency(controller.signal).then(res => {
      setEfficiency(res.data); setLoadingEffic(false);
    });
    dashboardService.fetchRecentOperations(controller.signal).then(res => {
      setOperations(res.data); setLoadingOps(false);
    });
    dashboardService.fetchTasks(controller.signal).then(res => {
      setTasks(res.data); setLoadingTasks(false);
    });

    return () => controller.abort();
  }, [range]);

  useEffect(() => {
    const cleanup = loadPage(range);
    return cleanup;
  }, [range]);

  const handleRangeChange = (r) => {
    setRange(r);
    setLoadingStats(true);
    setLoadingChart(true);
    dashboardService.fetchStats(r).then(res => { setStats(res.data); setLoadingStats(false); });
    dashboardService.fetchRevenueChart(r).then(res => { setChartData(res.data); setLoadingChart(false); });
  };

  const titleAnim = useAnimateIn(0);

  return (
    <>
      <GlobalStyles />
      <div className={shell.appShell}>

        <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />

        <div className={shell.mainArea}>

          <Header breadcrumbs={["Prime ERP", "Analytics", "Executive Dashboard"]} />

          <main className={shell.page} style={{ padding: "28px 32px", fontFamily: "'DM Sans','Segoe UI',sans-serif" }}>

            <div ref={titleAnim.ref} style={{
              display: "flex", justifyContent: "space-between", alignItems: "flex-start",
              marginBottom: 24, ...titleAnim.style,
            }}>
              <div>
                <h1 style={{ fontSize: 26, fontWeight: 800, color: T.text, margin: "0 0 4px", letterSpacing: "-0.5px" }}>
                  Analytics Overview
                </h1>
                <p style={{ fontSize: 14, color: T.textMuted, margin: 0 }}>
                  Monitor your enterprise performance across all key modules.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <div style={{ display: "flex", background: T.borderSoft, borderRadius: 8, padding: 3, gap: 2 }}>
                  {["weekly","monthly","yearly"].map(r => (
                    <button key={r} onClick={() => handleRangeChange(r)} style={{
                      padding: "5px 14px", border: "none", borderRadius: 6,
                      fontSize: 12, fontWeight: 600, cursor: "pointer",
                      background: range === r ? T.primary : "transparent",
                      color:      range === r ? "#fff"    : T.textMuted,
                      transition: "all 0.15s", textTransform: "capitalize",
                    }}>
                      {r}
                    </button>
                  ))}
                </div>
                <button style={{
                  padding: "0 12px", height: 34, border: `1px solid ${T.border}`,
                  borderRadius: 8, background: T.surface, cursor: "pointer",
                  fontSize: 12, fontWeight: 600, color: T.textMuted,
                  display: "inline-flex", alignItems: "center", gap: 6,
                }}>
                  <Settings size={15} aria-hidden="true" />
                  Settings
                </button>
                <button style={{
                  padding: "0 12px", height: 34, border: `1px solid ${T.border}`,
                  borderRadius: 8, background: T.surface, cursor: "pointer",
                  fontSize: 12, fontWeight: 600, color: T.textMuted,
                  display: "inline-flex", alignItems: "center", gap: 6,
                }}>
                  <Download size={15} aria-hidden="true" />
                  Export
                </button>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, marginBottom: 24 }}>
              {loadingStats
                ? Array.from({ length: 5 }).map((_, i) => <StatCard key={i} loading delay={i * 60} />)
                : stats.map((stat, i) => <StatCard key={stat.id} stat={stat} delay={i * 60} />)
              }
            </div>

            <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
              <RevenueChart
                data={chartData}
                loading={loadingChart}
                range={range}
                onRangeChange={handleRangeChange}
              />
              <AIInsightsPanel />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 24 }}>
              <div style={{ ...cardStyle }}>
                <EfficiencyChart data={efficiency} loading={loadingEffic} />
              </div>
              <div style={{ ...cardStyle }}>
                <RecentOperations ops={operations} loading={loadingOps} />
              </div>
              <ExecutiveTasks tasks={tasks} loading={loadingTasks} />
            </div>

            <div style={{ ...cardStyle, marginBottom: 0 }}>
              <EnterpriseShortcuts navigate={navigate} />
            </div>

          </main>

          <Footer />
        </div>
      </div>
    </>
  );
}
