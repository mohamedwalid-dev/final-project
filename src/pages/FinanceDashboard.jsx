/**
 * 💰 Finance Agent Dashboard — v5.0 PRODUCTION FIXED
 * =====================================================
 * FIXES:
 *   ✅ API_BASE hardcoded to localhost:9000
 *   ✅ Dashboard metrics parsed from action_stats.summary (real structure)
 *   ✅ Active escalations → invoice queue (ai_risk_score is 0-100, normalized to 0-1)
 *   ✅ Recent actions rendered correctly
 *   ✅ Polling every 10s for live data (no WebSocket dependency)
 *   ✅ Collection strategy shown per invoice
 *   ✅ Amount exposure chart from real escalation data
 *   ✅ All edge cases handled (null ai_decision, missing fields)
 */

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  AlertTriangle, CheckCircle, Clock, TrendingDown,
  Zap, RefreshCw, Activity, Scale, Ban,
  FileText, Bell, Mail, Shield, Loader2,
  Cpu, X, ArrowUp, User, Gavel,
  AlertCircle, CheckSquare, MinusSquare,
  DollarSign, Send, Database,
} from "lucide-react";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";


// ═══════════════════════════════════════════════════════════════════
// ⚙️  CONFIG — fix الـ port هنا
// ═══════════════════════════════════════════════════════════════════

const API_BASE = "http://localhost:9000";
const POLL_MS  = 10_000; // refresh كل 10 ثواني

// ═══════════════════════════════════════════════════════════════════
// 🔌 API CLIENT
// ═══════════════════════════════════════════════════════════════════

const apiFetch = async (path, opts = {}) => {
  const ctrl = new AbortController();
  const tid  = setTimeout(() => ctrl.abort(), 15_000);
  try {
    const r = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      signal: ctrl.signal,
      ...opts,
    });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  } finally {
    clearTimeout(tid);
  }
};

// ═══════════════════════════════════════════════════════════════════
// 🎭 CONSTANTS
// ═══════════════════════════════════════════════════════════════════

const STRATEGY_META = {
  aggressive: { color: "#E03131", bg: "#FFF5F5", label: "Aggressive" },
  standard:   { color: "#F59F00", bg: "#FFF9DB", label: "Standard"   },
  soft:       { color: "#2F9E44", bg: "#EBFBEE", label: "Soft"       },
};

const PRIORITY_META = {
  critical: { color: "#E03131", bg: "#FFF5F5", dot: "#E03131" },
  high:     { color: "#E8590C", bg: "#FFF4E6", dot: "#E8590C" },
  medium:   { color: "#F59F00", bg: "#FFF9DB", dot: "#F59F00" },
  low:      { color: "#2F9E44", bg: "#EBFBEE", dot: "#2F9E44" },
};

const ACTION_ICON = {
  email:                 Mail,
  internal_notification: Bell,
  legal_escalation:      Scale,
  system:                Cpu,
  escalation:            ArrowUp,
  followup_scheduled:    Clock,
};

const RISK_COLOR = (s) => s >= 0.7 ? "#E03131" : s >= 0.45 ? "#F59F00" : "#2F9E44";
const RISK_LABEL = (s) => s >= 0.7 ? "High"    : s >= 0.45 ? "Medium"  : "Low";

const fmtK   = (n) => !n ? "0" : n >= 1e6 ? `${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `${(n/1e3).toFixed(0)}K` : String(Math.round(n));
const fmtEGP = (n) => `${(n || 0).toLocaleString("en-EG", { maximumFractionDigits: 0 })} EGP`;
const fmtTime = (s) => {
  if (!s) return "—";
  try { return new Date(s).toLocaleTimeString("en-EG", { hour: "2-digit", minute: "2-digit" }); }
  catch { return "—"; }
};
const nowStr = () => new Date().toLocaleTimeString("en-EG", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

// ═══════════════════════════════════════════════════════════════════
// 🧱 SMALL UI COMPONENTS
// ═══════════════════════════════════════════════════════════════════

const Spinner = ({ size = 16 }) => (
  <Loader2 size={size} style={{ animation: "spin .8s linear infinite", flexShrink: 0 }} />
);

const Badge = ({ label, color, bg }) => (
  <span style={{
    fontSize: 11, padding: "3px 8px", borderRadius: 6,
    fontWeight: 700, background: bg, color, whiteSpace: "nowrap",
    display: "inline-flex", alignItems: "center",
  }}>{label}</span>
);

const StrategyBadge = ({ strategy }) => {
  const m = STRATEGY_META[strategy] || STRATEGY_META.standard;
  return <Badge label={m.label} color={m.color} bg={m.bg} />;
};

const RiskBadge = ({ score }) => {
  const label = RISK_LABEL(score);
  const color = RISK_COLOR(score);
  const bg    = score >= 0.7 ? "#FFF5F5" : score >= 0.45 ? "#FFF9DB" : "#EBFBEE";
  return <Badge label={label} color={color} bg={bg} />;
};

const PriorityDot = ({ priority }) => {
  const m = PRIORITY_META[priority] || PRIORITY_META.low;
  return <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: m.dot, flexShrink: 0 }} />;
};

function MetricCard({ label, value, sub, icon: Icon, color = "#3B5BDB", loading }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 12, padding: "20px 22px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 11, color: "#868E96", fontWeight: 600, letterSpacing: ".3px", textTransform: "uppercase" }}>{label}</span>
        {Icon && (
          <div style={{ width: 32, height: 32, borderRadius: 8, background: `${color}18`, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon size={15} style={{ color }} />
          </div>
        )}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: "#212529", letterSpacing: "-.8px", marginBottom: 6, minHeight: 36, display: "flex", alignItems: "center" }}>
        {loading ? <Spinner size={20} /> : value}
      </div>
      <div style={{ fontSize: 12, color: "#ADB5BD" }}>{sub}</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// 📊 CHARTS  — من بيانات حقيقية
// ═══════════════════════════════════════════════════════════════════

function ChartsRow({ dashData, escalations }) {
  // Action type breakdown من action_stats.breakdown
  const actionBreakdown = useMemo(() => {
    const breakdown = dashData?.action_stats?.breakdown || [];
    const merged = {};
    breakdown.forEach(({ action_type, count }) => {
      merged[action_type] = (merged[action_type] || 0) + count;
    });
    const COLORS = {
      email:                 "#3B5BDB",
      internal_notification: "#7048E8",
      legal_escalation:      "#E03131",
      system:                "#F59F00",
      escalation:            "#E8590C",
      followup_scheduled:    "#2F9E44",
    };
    return Object.entries(merged)
      .map(([k, v]) => ({ name: k.replace(/_/g, " "), value: v, color: COLORS[k] || "#ADB5BD" }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6);
  }, [dashData]);

  // Risk distribution from escalations (ai_risk_score 0-100)
  const riskDist = useMemo(() => {
    const items = escalations;
    const high   = items.filter(i => (i.ai_risk_score || 0) >= 70).length;
    const medium = items.filter(i => (i.ai_risk_score || 0) >= 45 && (i.ai_risk_score || 0) < 70).length;
    const low    = items.filter(i => (i.ai_risk_score || 0) < 45).length;
    return [
      { name: "High",   value: high,   color: "#E03131" },
      { name: "Medium", value: medium, color: "#F59F00" },
      { name: "Low",    value: low,    color: "#2F9E44" },
    ].filter(d => d.value > 0);
  }, [escalations]);

  // Amount by strategy
  const amountByStrategy = useMemo(() => {
    const groups = {};
    escalations.forEach(i => {
      const k = i.collection_strategy || "standard";
      groups[k] = (groups[k] || 0) + (i.amount || 0);
    });
    return Object.entries(groups).map(([k, v]) => ({
      name: k.charAt(0).toUpperCase() + k.slice(1),
      amt:  Math.round(v),
      color: (STRATEGY_META[k] || STRATEGY_META.standard).color,
    }));
  }, [escalations]);

  const noData = escalations.length === 0 && actionBreakdown.length === 0;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 16 }}>

      {/* Action Breakdown */}
      <div style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 12, padding: "18px 20px" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#212529", marginBottom: 2 }}>Action Breakdown</div>
        <div style={{ fontSize: 11, color: "#ADB5BD", marginBottom: 14 }}>30-day period</div>
        {actionBreakdown.length > 0 ? (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={actionBreakdown} layout="vertical" barSize={10}>
              <XAxis type="number" tick={{ fontSize: 10, fill: "#ADB5BD" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "#495057" }} axisLine={false} tickLine={false} width={100} />
              <Tooltip formatter={(v) => [v.toLocaleString(), "count"]} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {actionBreakdown.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center", color: "#ADB5BD", fontSize: 12 }}>
            {noData ? "Run cycle to load data" : "Loading…"}
          </div>
        )}
      </div>

      {/* Risk Distribution */}
      <div style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 12, padding: "18px 20px" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#212529", marginBottom: 2 }}>Escalation Risk</div>
        <div style={{ fontSize: 11, color: "#ADB5BD", marginBottom: 14 }}>{escalations.length} active escalations</div>
        {riskDist.length > 0 ? (
          <>
            <ResponsiveContainer width="100%" height={120}>
              <PieChart>
                <Pie data={riskDist} cx="50%" cy="50%" innerRadius={32} outerRadius={55} paddingAngle={2} dataKey="value">
                  {riskDist.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                <Tooltip formatter={(v, n) => [v, n]} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 8, flexWrap: "wrap" }}>
              {riskDist.map(d => (
                <span key={d.name} style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: d.color }} />
                  <span style={{ color: "#868E96" }}>{d.name} ({d.value})</span>
                </span>
              ))}
            </div>
          </>
        ) : (
          <div style={{ height: 140, display: "flex", alignItems: "center", justifyContent: "center", color: "#ADB5BD", fontSize: 12 }}>
            No escalation data
          </div>
        )}
      </div>

      {/* Amount by Strategy */}
      <div style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 12, padding: "18px 20px" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#212529", marginBottom: 2 }}>Exposure by Strategy</div>
        <div style={{ fontSize: 11, color: "#ADB5BD", marginBottom: 14 }}>EGP total per collection strategy</div>
        {amountByStrategy.length > 0 ? (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={amountByStrategy} barSize={28}>
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#ADB5BD" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#ADB5BD" }} axisLine={false} tickLine={false} tickFormatter={v => fmtK(v)} />
              <Tooltip formatter={(v) => [fmtEGP(v), "Amount"]} />
              <Bar dataKey="amt" radius={[4, 4, 0, 0]}>
                {amountByStrategy.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center", color: "#ADB5BD", fontSize: 12 }}>
            No strategy data
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// 📋 ESCALATIONS TABLE
// ═══════════════════════════════════════════════════════════════════

function EscalationsTable({ items, loading, onSelect, selectedId }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "16px 22px", borderBottom: "1px solid #E9ECEF", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#212529" }}>Active Escalations Queue</div>
          <div style={{ fontSize: 11, color: "#ADB5BD", marginTop: 2 }}>from /finance/actions/dashboard-data — click to inspect</div>
        </div>
        <span style={{ fontSize: 12, color: "#868E96", background: "#F8F9FA", border: "1px solid #E9ECEF", padding: "3px 10px", borderRadius: 6, fontWeight: 600 }}>
          {items.length} invoices
        </span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #F1F3F5", background: "#FAFAFA" }}>
              {["Invoice", "Customer", "Amount", "Overdue", "Risk Score", "Strategy", "Status"].map(h => (
                <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#ADB5BD", textTransform: "uppercase", letterSpacing: ".5px", whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ textAlign: "center", padding: 40, color: "#ADB5BD" }}><Spinner /></td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: "center", padding: 40, fontSize: 13, color: "#ADB5BD" }}>
                No active escalations. Click <strong>Run Cycle</strong> to scan.
              </td></tr>
            ) : items.map((inv, i) => {
              const riskScore  = (inv.ai_risk_score || 0) / 100; // API returns 0-100
              const rc         = RISK_COLOR(riskScore);
              const isSelected = selectedId === inv.invoice_id;
              return (
                <tr key={inv.invoice_id || i}
                  onClick={() => onSelect(inv)}
                  style={{
                    borderBottom: "1px solid #F8F9FA",
                    background: isSelected ? "#F5F9FF" : "transparent",
                    cursor: "pointer", transition: "background .1s",
                  }}
                  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = "#FAFAFA"; }}
                  onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
                >
                  <td style={{ padding: "9px 14px", fontFamily: "monospace", fontSize: 12, color: "#ADB5BD" }}>#{inv.invoice_id}</td>
                  <td style={{ padding: "9px 14px", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#212529", fontWeight: 500 }}>{inv.customer_name || `Customer ${inv.customer_id}`}</td>
                  <td style={{ padding: "9px 14px", color: "#495057", fontWeight: 600, whiteSpace: "nowrap" }}>{fmtEGP(inv.amount)}</td>
                  <td style={{ padding: "9px 14px" }}>
                    <span style={{ fontWeight: 600, color: inv.overdue_days >= 90 ? "#E03131" : inv.overdue_days >= 45 ? "#E8590C" : "#F59F00" }}>
                      {inv.overdue_days}d
                    </span>
                  </td>
                  <td style={{ padding: "9px 14px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{ width: 44, height: 5, background: "#F1F3F5", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${Math.round(inv.ai_risk_score || 0)}%`, background: rc }} />
                      </div>
                      <span style={{ fontSize: 11, color: rc, fontWeight: 700, fontFamily: "monospace" }}>{Math.round(inv.ai_risk_score || 0)}%</span>
                    </div>
                  </td>
                  <td style={{ padding: "9px 14px" }}><StrategyBadge strategy={inv.collection_strategy} /></td>
                  <td style={{ padding: "9px 14px" }}>
                    <span style={{ fontSize: 11, color: "#E8590C", fontWeight: 600 }}>{inv.status || "overdue"}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// 🕐 RECENT ACTIONS FEED
// ═══════════════════════════════════════════════════════════════════

function RecentActions({ actions }) {
  if (!actions.length) {
    return (
      <div style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 12, padding: "20px 22px" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#212529", marginBottom: 12 }}>Recent Actions</div>
        <div style={{ fontSize: 13, color: "#ADB5BD", textAlign: "center", padding: "20px 0" }}>No actions yet</div>
      </div>
    );
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "16px 22px", borderBottom: "1px solid #E9ECEF" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#212529" }}>Recent Actions</div>
        <div style={{ fontSize: 11, color: "#ADB5BD", marginTop: 2 }}>Latest {actions.length} executed actions</div>
      </div>
      <div style={{ maxHeight: 380, overflowY: "auto" }}>
        {actions.map((a, i) => {
          const Icon  = ACTION_ICON[a.action_type] || Activity;
          const pm    = PRIORITY_META[a.priority] || PRIORITY_META.low;
          return (
            <div key={a.id || i} style={{
              padding: "12px 22px", borderBottom: "1px solid #F8F9FA",
              display: "flex", gap: 12, alignItems: "flex-start",
            }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: pm.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Icon size={14} style={{ color: pm.color }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#212529", fontFamily: "monospace" }}>#{a.invoice_id}</span>
                  <span style={{ fontSize: 11, color: "#868E96" }}>{a.action_type?.replace(/_/g, " ")}</span>
                  <PriorityDot priority={a.priority} />
                  <span style={{ fontSize: 10, color: pm.color, fontWeight: 600 }}>{a.priority?.toUpperCase()}</span>
                  <span style={{ marginLeft: "auto", fontSize: 10, color: "#ADB5BD" }}>{fmtTime(a.sent_at)}</span>
                </div>
                <div style={{ fontSize: 11, color: "#868E96", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {a.subject || a.template_name || "—"}
                </div>
              </div>
              <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: a.status === "sent" || a.status === "executed" || a.status === "escalated" ? "#EBFBEE" : "#FFF9DB", color: a.status === "sent" || a.status === "executed" || a.status === "escalated" ? "#2F9E44" : "#F59F00", fontWeight: 600, flexShrink: 0 }}>
                {a.status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// 🔍 INVOICE DETAIL DRAWER
// ═══════════════════════════════════════════════════════════════════

function InvoiceDrawer({ invoice, onClose, onRunAction }) {
  const [loading, setLoading] = useState(false);

  if (!invoice) return null;

  const riskScore = (invoice.ai_risk_score || 0) / 100;
  const rc = RISK_COLOR(riskScore);

  const handleAction = async (actionType) => {
    setLoading(true);
    try {
      await apiFetch("/finance/actions/execute", {
        method: "POST",
        body: JSON.stringify({
          action:      actionType,
          invoice_id:  invoice.invoice_id,
          customer_id: invoice.customer_id,
          amount:      invoice.amount || 0,
          decision:    "manual_trigger",
          reason:      `Manual ${actionType} triggered from dashboard`,
        }),
      });
      onRunAction?.();
      onClose();
    } catch (e) {
      alert(`Action failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.3)", zIndex: 998, backdropFilter: "blur(3px)" }} />
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: 440,
        background: "#fff", borderLeft: "1px solid #E9ECEF", zIndex: 999,
        display: "flex", flexDirection: "column", overflowY: "auto",
        boxShadow: "-8px 0 40px rgba(0,0,0,.12)", animation: "slideRight .22s ease",
      }}>
        {/* Header */}
        <div style={{ padding: "20px 22px", borderBottom: "1px solid #E9ECEF", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#212529", fontFamily: "monospace" }}>Invoice #{invoice.invoice_id}</div>
            <div style={{ fontSize: 13, color: "#868E96", marginTop: 2 }}>{invoice.customer_name}</div>
          </div>
          <button onClick={onClose} style={{ background: "#F8F9FA", border: "1px solid #E9ECEF", borderRadius: 8, cursor: "pointer", padding: "6px 8px", display: "flex" }}>
            <X size={15} style={{ color: "#868E96" }} />
          </button>
        </div>

        {/* Risk gauge */}
        <div style={{ padding: "18px 22px", borderBottom: "1px solid #F1F3F5", background: "#FAFAFA" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ position: "relative", width: 64, height: 64 }}>
              <svg width="64" height="64" style={{ transform: "rotate(-90deg)" }}>
                <circle cx="32" cy="32" r="26" fill="none" stroke="#F1F3F5" strokeWidth="6" />
                <circle cx="32" cy="32" r="26" fill="none" stroke={rc} strokeWidth="6"
                  strokeDasharray={`${Math.round(riskScore * 163.4)} 163.4`} strokeLinecap="round" />
              </svg>
              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, color: rc }}>
                {Math.round(invoice.ai_risk_score || 0)}%
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#868E96", marginBottom: 4 }}>AI Risk Score</div>
              <RiskBadge score={riskScore} />
              <div style={{ marginTop: 6 }}><StrategyBadge strategy={invoice.collection_strategy} /></div>
            </div>
            <div style={{ marginLeft: "auto", textAlign: "right" }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#212529" }}>{fmtEGP(invoice.amount)}</div>
              <div style={{ fontSize: 12, color: "#E03131", marginTop: 2, fontWeight: 600 }}>{invoice.overdue_days} days overdue</div>
            </div>
          </div>
        </div>

        {/* Details */}
        <div style={{ padding: "18px 22px", borderBottom: "1px solid #F1F3F5" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#868E96", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 12 }}>Invoice Details</div>
          {[
            ["Status",     invoice.status],
            ["Strategy",   invoice.collection_strategy],
            ["AI Decision", invoice.ai_decision || "Pending AI decision"],
            ["Actions Taken", invoice.action_count ?? 0],
            ["Last Action", fmtTime(invoice.last_action_at)],
          ].map(([label, val]) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #F8F9FA", fontSize: 13 }}>
              <span style={{ color: "#868E96" }}>{label}</span>
              <span style={{ color: "#212529", fontWeight: 600 }}>{String(val || "—")}</span>
            </div>
          ))}
        </div>

        {/* Manual actions */}
        <div style={{ padding: "18px 22px", borderBottom: "1px solid #F1F3F5" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#868E96", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 12 }}>Manual Actions</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {[
              { label: "Send Reminder Email",  action: "send_polite_reminder",   color: "#3B5BDB", bg: "#EDF2FF" },
              { label: "Hard Follow-up",       action: "send_urgent_notice",     color: "#E8590C", bg: "#FFF4E6" },
              { label: "Propose Payment Plan", action: "propose_payment_plan",   color: "#7048E8", bg: "#F3F0FF" },
              { label: "Escalate to Legal",    action: "escalate_to_legal",      color: "#E03131", bg: "#FFF5F5" },
            ].map(({ label, action, color, bg }) => (
              <button key={action}
                onClick={() => handleAction(action)}
                disabled={loading}
                style={{ padding: "10px 14px", borderRadius: 8, border: `1px solid ${color}40`, background: bg, color, fontSize: 12, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1, textAlign: "left", display: "flex", alignItems: "center", gap: 8 }}>
                {loading ? <Spinner size={12} /> : <Send size={12} />} {label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ padding: "18px 22px", marginTop: "auto" }}>
          <button onClick={onClose} style={{ width: "100%", padding: 10, borderRadius: 8, background: "#F8F9FA", border: "1px solid #E9ECEF", color: "#868E96", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
            Close
          </button>
        </div>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════
// 🎯 MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════

export default function FinanceAgentDashboard() {
  const [dashData,     setDashData]     = useState(null);
  const [logData,      setLogData]      = useState(null);
  const [loading,      setLoading]      = useState(true);
  const [running,      setRunning]      = useState(false);
  const [error,        setError]        = useState(null);
  const [lastRefresh,  setLastRefresh]  = useState(null);
  const [selected,     setSelected]     = useState(null);
  const [connected,    setConnected]    = useState(false);

  const pollRef    = useRef(null);
  const runningRef = useRef(false);

  // ── Fetch all data ──────────────────────────────────────────────
  const fetchAll = useCallback(async (silent = false) => {
    if (!silent) setError(null);
    try {
      const [dash, log] = await Promise.all([
        apiFetch("/finance/actions/dashboard-data?days=30"),
        apiFetch("/finance/actions/log?limit=100"),
      ]);
      setDashData(dash);
      setLogData(log);
      setConnected(true);
      setLastRefresh(nowStr());
    } catch (e) {
      setConnected(false);
      if (!silent) setError(`Connection failed: ${e.message} — check backend is running on port 9000`);
    }
  }, []);

  // Initial load + polling
  useEffect(() => {
    (async () => {
      setLoading(true);
      await fetchAll(false);
      setLoading(false);
    })();

    // Start polling
    pollRef.current = setInterval(() => fetchAll(true), POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [fetchAll]);

  // ── Run cycle (trigger backend scans) ──────────────────────────
  const runCycle = useCallback(async () => {
    if (runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    setError(null);
    try {
      await Promise.all([
        apiFetch("/trigger/run-now/overdue-invoices", { method: "POST" }).catch(() => {}),
        apiFetch("/trigger/run-now/new-invoices",     { method: "POST" }).catch(() => {}),
      ]);
      // Wait for backend to process then refresh
      await new Promise(r => setTimeout(r, 1500));
      await fetchAll(false);
    } catch (e) {
      setError(e.message);
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  }, [fetchAll]);

  // Ctrl+Enter shortcut
  useEffect(() => {
    const h = (e) => { if (e.ctrlKey && e.key === "Enter") runCycle(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [runCycle]);

  // ── Parse dashboard data (real API structure) ──────────────────
  const summary     = dashData?.action_stats?.summary     || {};
  const escalations = dashData?.active_escalations?.items || [];
  const legalCases  = dashData?.legal_cases?.items        || [];
  const recentActs  = dashData?.recent_actions            || [];

  // Metrics from real API fields
  const totalActions     = summary.total              || 0;
  const criticalActions  = summary.critical_actions   || 0;
  const legalEscalations = summary.legal_escalations  || 0;
  const emailsSent       = summary.emails_sent        || 0;

  const totalExposure    = useMemo(() =>
    escalations.reduce((s, i) => s + (i.amount || 0), 0), [escalations]
  );
  const highRiskCount    = useMemo(() =>
    escalations.filter(i => (i.ai_risk_score || 0) >= 70).length, [escalations]
  );

  return (
    <div style={{ minHeight: "100vh", background: "#F8F9FA", padding: "28px 32px 60px", fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        @keyframes spin       { to { transform: rotate(360deg); } }
        @keyframes slideRight { from { transform: translateX(30px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes slideDown  { from { transform: translateY(-8px); opacity: 0; } to { opacity: 1; } }
        * { box-sizing: border-box; }
        body { font-family: 'DM Sans', system-ui, sans-serif; }
        .btn { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; padding: 8px 14px; border-radius: 8px; border: none; cursor: pointer; transition: all .15s; font-family: inherit; }
        .btn:disabled { opacity: .5; cursor: not-allowed; }
        .btn-primary  { background: #212529; color: #fff; }
        .btn-primary:hover:not(:disabled) { background: #343A40; box-shadow: 0 4px 14px rgba(33,37,41,.25); }
        .btn-ghost    { background: #fff; color: #495057; border: 1px solid #E9ECEF; }
        .btn-ghost:hover:not(:disabled) { background: #F8F9FA; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #DEE2E6; border-radius: 4px; }
        .mono { font-family: 'JetBrains Mono', monospace; }
      `}</style>

      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700, color: "#212529", margin: 0, marginBottom: 6, letterSpacing: "-.5px" }}>
              Finance Collection Engine
            </h1>
            <div style={{ fontSize: 13, color: "#868E96", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: connected ? "#2F9E44" : "#E03131" }} />
              {loading ? "Connecting to localhost:9000…" : connected ? "Connected to localhost:9000" : "Disconnected — backend unreachable"}
              {lastRefresh && (
                <span style={{ fontSize: 11, color: "#ADB5BD", marginLeft: 4 }}>· refreshed {lastRefresh}</span>
              )}
              <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6, fontWeight: 600, background: "#F8F9FA", color: "#ADB5BD", border: "1px solid #E9ECEF" }}>
                Polling {POLL_MS / 1000}s
              </span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost" onClick={() => fetchAll(false)} disabled={loading}>
              <RefreshCw size={13} /> Refresh
            </button>
            <button className="btn btn-primary" onClick={runCycle} disabled={running}>
              {running ? <Spinner size={13} /> : <Zap size={13} />}
              {running ? "Running…" : "Run Cycle"}
            </button>
          </div>
        </div>
      </div>

      {/* ── Error banner ── */}
      {error && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#FFF5F5", border: "1px solid #FFD8D8", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#C92A2A", marginBottom: 20, animation: "slideDown .3s" }}>
          <AlertTriangle size={14} /> {error}
          <button onClick={() => setError(null)} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "#C92A2A" }}><X size={13} /></button>
        </div>
      )}

      {/* ── Metric Cards ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 20 }}>
        <MetricCard
          label="Total Exposure"
          value={fmtEGP(totalExposure)}
          sub={`${escalations.length} active escalations`}
          icon={TrendingDown}
          color="#E03131"
          loading={loading}
        />
        <MetricCard
          label="Total Actions"
          value={totalActions.toLocaleString()}
          sub="last 30 days"
          icon={Activity}
          color="#3B5BDB"
          loading={loading}
        />
        <MetricCard
          label="Legal Escalations"
          value={legalEscalations.toLocaleString()}
          sub={`${dashData?.legal_cases?.count || 0} open cases`}
          icon={Scale}
          color="#E03131"
          loading={loading}
        />
        <MetricCard
          label="Critical Actions"
          value={criticalActions.toLocaleString()}
          sub={`${emailsSent.toLocaleString()} emails sent`}
          icon={AlertTriangle}
          color="#E8590C"
          loading={loading}
        />
      </div>

      {/* ── Summary Stats Row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 20 }}>
        {[
          { label: "Emails Sent",     val: summary.emails_sent,       icon: Mail,     color: "#3B5BDB" },
          { label: "Notifications",   val: summary.notifications,     icon: Bell,     color: "#7048E8" },
          { label: "System Actions",  val: summary.system_actions,    icon: Cpu,      color: "#F59F00" },
          { label: "Follow-ups",      val: summary.followups,         icon: Clock,    color: "#2F9E44" },
          { label: "High Risk",       val: highRiskCount,             icon: Shield,   color: "#E03131" },
        ].map(({ label, val, icon: Icon, color }) => (
          <div key={label} style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 10, padding: "12px 16px", display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 28, height: 28, borderRadius: 6, background: `${color}15`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Icon size={13} style={{ color }} />
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "#212529" }}>{loading ? "—" : (val || 0).toLocaleString()}</div>
              <div style={{ fontSize: 10, color: "#ADB5BD", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".4px" }}>{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Charts ── */}
      <ChartsRow dashData={dashData} escalations={escalations} />

      {/* ── Main content grid ── */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 16 }}>
        <EscalationsTable
          items={escalations}
          loading={loading}
          onSelect={setSelected}
          selectedId={selected?.invoice_id}
        />

        {/* System Status */}
        <div style={{ background: "#fff", border: "1px solid #E9ECEF", borderRadius: 12, padding: "20px 22px", display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: "#212529", margin: 0, marginBottom: 14 }}>System Status</h3>
            {[
              { label: "Escalations",      val: dashData?.active_escalations?.count ?? "—" },
              { label: "Legal Cases",      val: dashData?.legal_cases?.count ?? "—",    color: legalEscalations > 0 ? "#E03131" : undefined },
              { label: "Period",           val: `${dashData?.period_days || 30} days` },
              { label: "Total Actions",    val: totalActions.toLocaleString() },
              { label: "Critical Actions", val: criticalActions.toLocaleString(), color: criticalActions > 0 ? "#E03131" : undefined },
            ].map(({ label, val, color }) => (
              <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #F8F9FA" }}>
                <span style={{ fontSize: 13, color: "#868E96" }}>{label}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: color || "#212529" }}>{val}</span>
              </div>
            ))}
          </div>

          {/* Endpoints status */}
          <div style={{ borderTop: "1px solid #F1F3F5", paddingTop: 16 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: "#212529", margin: 0, marginBottom: 12 }}>Data Sources</h3>
            {[
              { label: "/finance/actions/dashboard-data", ok: dashData !== null },
              { label: "/finance/actions/log",            ok: logData  !== null },
              { label: "/trigger/run-now/*",              ok: connected },
            ].map(({ label, ok }) => (
              <div key={label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "5px 0", fontSize: 11 }}>
                <span className="mono" style={{ color: "#868E96", fontSize: 10 }}>{label}</span>
                <span style={{ color: ok ? "#2F9E44" : "#ADB5BD", fontWeight: 700 }}>{ok ? "✓ live" : "– offline"}</span>
              </div>
            ))}
          </div>

          {/* Action summary breakdown */}
          {dashData?.action_stats?.breakdown?.length > 0 && (
            <div style={{ borderTop: "1px solid #F1F3F5", paddingTop: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: "#212529", margin: 0, marginBottom: 12 }}>By Priority</h3>
              {["critical", "high", "medium", "low"].map(priority => {
                const rows = dashData.action_stats.breakdown.filter(b => b.priority === priority);
                const count = rows.reduce((s, r) => s + r.count, 0);
                if (!count) return null;
                const pm = PRIORITY_META[priority];
                return (
                  <div key={priority} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #F8F9FA" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#868E96", textTransform: "capitalize" }}>
                      <PriorityDot priority={priority} /> {priority}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: pm.color }}>{count.toLocaleString()}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Recent Actions ── */}
      <RecentActions actions={recentActs} />

      {/* ── Drawer ── */}
      {selected && (
        <InvoiceDrawer
          invoice={selected}
          onClose={() => setSelected(null)}
          onRunAction={() => fetchAll(false)}
        />
      )}
    </div>
  );
}