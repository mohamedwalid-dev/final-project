// Pages/SalesPage.jsx
// Pure JS - no TypeScript
// 4 tabs: Lead Pipeline (Kanban), Sales Analytics, Product Catalog, Customers & Orders
// Drag-to-reorder columns, inline card edit, priority badges
// Full Sales Analytics with Recharts
// Product Catalog with search/filter/add
// Customers & Orders table
// Same Sidebar + Header structure as all other pages

import { useState, useRef, useCallback, useMemo, useEffect, memo } from "react";
import { useNavigate } from "react-router-dom";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from "recharts";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header from "../components/Finance/Layout/Header";
import s from "../styles/SalesPage.module.css";
import shell from "../styles/AppShell.module.css";
import {
  ChartNoAxesCombined,
  CheckCircle2,
  CircleDollarSign,
  ClipboardList,
  Clock3,
  Cloud,
  Crown,
  Download,
  Eye,
  HardDrive,
  Laptop,
  Mail,
  MoreHorizontal,
  Package,
  Pencil,
  Plus,
  RefreshCcw,
  Search,
  ShoppingCart,
  SlidersHorizontal,
  Target,
  Trash2,
  UserRoundPlus,
  Users,
  Wrench,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
// ── MOCK DATA
// ─────────────────────────────────────────────────────────────────────────────

const PIPELINE_COLS = [
  { id: "prospecting",   label: "Prospecting",   color: "#3B5BDB" },
  { id: "qualification", label: "Qualification", color: "#F59F00" },
  { id: "proposal",      label: "Proposal",      color: "#845EF7" },
  { id: "negotiation",   label: "Negotiation",   color: "#F76707" },
  { id: "closed_won",    label: "Closed Won",    color: "#2F9E44" },
];

const INITIAL_LEADS = [
  { id: "l1", company: "Acme Dynamics",     amount: 12500, priority: "HIGH",   days: 2,  stage: "prospecting",   assignee: "AS", assigneeColor: "#3B5BDB" },
  { id: "l2", company: "Global Tech Corp",  amount: 8200,  priority: "MEDIUM", days: 5,  stage: "prospecting",   assignee: "MT", assigneeColor: "#F59F00" },
  { id: "l3", company: "Innovate AI",       amount: 45000, priority: "HIGH",   days: 12, stage: "qualification", assignee: "SJ", assigneeColor: "#845EF7" },
  { id: "l4", company: "Starlight Retail",  amount: 3400,  priority: "LOW",    days: 1,  stage: "qualification", assignee: "DC", assigneeColor: "#2F9E44" },
  { id: "l5", company: "Nexus Logistics",   amount: 22000, priority: "MEDIUM", days: 8,  stage: "proposal",      assignee: "ER", assigneeColor: "#FA5252" },
  { id: "l6", company: "Cloud Scale Inc",   amount: 88000, priority: "HIGH",   days: 15, stage: "negotiation",   assignee: "AS", assigneeColor: "#3B5BDB" },
  { id: "l7", company: "DataBridge Corp",   amount: 31000, priority: "HIGH",   days: 3,  stage: "closed_won",    assignee: "MT", assigneeColor: "#F59F00" },
  { id: "l8", company: "PulseWave Media",   amount: 7800,  priority: "LOW",    days: 6,  stage: "prospecting",   assignee: "SJ", assigneeColor: "#845EF7" },
  { id: "l9", company: "Vantage Systems",   amount: 54000, priority: "HIGH",   days: 20, stage: "negotiation",   assignee: "DC", assigneeColor: "#2F9E44" },
];

const PRIORITY_META = {
  HIGH:   { bg: "#FFF0F0", color: "#C92A2A", border: "#FFD8D8" },
  MEDIUM: { bg: "#FFF9EC", color: "#b07d00", border: "#FFE8A0" },
  LOW:    { bg: "#F0FFF4", color: "#22863a", border: "#B2F2BB" },
};

// ── Analytics Mock Data ───────────────────────────────────────────────────────
const MONTHLY_REVENUE = [
  { month: "Jan", revenue: 124000, target: 110000, deals: 18 },
  { month: "Feb", revenue: 138000, target: 120000, deals: 22 },
  { month: "Mar", revenue: 152000, target: 130000, deals: 25 },
  { month: "Apr", revenue: 141000, target: 140000, deals: 20 },
  { month: "May", revenue: 178000, target: 150000, deals: 29 },
  { month: "Jun", revenue: 195000, target: 160000, deals: 32 },
];

const PIPELINE_VALUE_BY_STAGE = [
  { stage: "Prospecting",   value: 45000,  fill: "#3B5BDB" },
  { stage: "Qualification", value: 72000,  fill: "#F59F00" },
  { stage: "Proposal",      value: 38000,  fill: "#845EF7" },
  { stage: "Negotiation",   value: 110000, fill: "#F76707" },
  { stage: "Closed Won",    value: 245000, fill: "#2F9E44" },
];

const WIN_LOSS_DATA = [
  { name: "Won", value: 68, fill: "#2F9E44" },
  { name: "Lost", value: 32, fill: "#FA5252" },
];

const TOP_REPS = [
  { name: "Alex Sterling",    deals: 24, revenue: 284000, quota: 92, avatar: "AS", color: "#3B5BDB" },
  { name: "Marcus Thompson",  deals: 19, revenue: 218000, quota: 87, avatar: "MT", color: "#F59F00" },
  { name: "Sarah Jenkins",    deals: 17, revenue: 196000, quota: 82, avatar: "SJ", color: "#845EF7" },
  { name: "David Chen",       deals: 14, revenue: 164000, quota: 71, avatar: "DC", color: "#2F9E44" },
  { name: "Elena Rodriguez",  deals: 11, revenue: 138000, quota: 65, avatar: "ER", color: "#FA5252" },
];

// ── Product Catalog Mock ──────────────────────────────────────────────────────
const INITIAL_PRODUCTS = [
  { id: "p1", name: "Enterprise Suite",      category: "Software",  price: 12000, sku: "SW-ENT-001", stock: "∞",   status: "Active",   description: "Full ERP platform license" },
  { id: "p2", name: "Analytics Pro",         category: "Software",  price: 3600,  sku: "SW-ANA-002", stock: "∞",   status: "Active",   description: "Advanced analytics & BI" },
  { id: "p3", name: "Cloud Storage 1TB",     category: "Cloud",     price: 1200,  sku: "CL-STR-001", stock: "∞",   status: "Active",   description: "Annual cloud storage plan" },
  { id: "p4", name: "Server Node X1",        category: "Hardware",  price: 8500,  sku: "HW-SRV-001", stock: 42,    status: "Active",   description: "High-performance compute node" },
  { id: "p5", name: "Support Package Gold",  category: "Services",  price: 4800,  sku: "SV-SPT-001", stock: "∞",   status: "Active",   description: "24/7 premium support SLA" },
  { id: "p6", name: "API Gateway Add-on",    category: "Software",  price: 2400,  sku: "SW-API-003", stock: "∞",   status: "Draft",    description: "REST & GraphQL API layer" },
  { id: "p7", name: "IoT Sensor Pack",       category: "Hardware",  price: 450,   sku: "HW-IOT-002", stock: 8,     status: "Low Stock",description: "Smart sensor cluster (12 units)" },
  { id: "p8", name: "Onboarding Workshop",   category: "Services",  price: 2000,  sku: "SV-ONB-001", stock: "∞",   status: "Active",   description: "2-day implementation workshop" },
];

const PRODUCT_CATEGORIES = ["All", "Software", "Hardware", "Cloud", "Services"];

// ── Customers Mock ────────────────────────────────────────────────────────────
const CUSTOMERS = [
  { id: "c1", company: "Acme Dynamics",    contact: "John Porter",    email: "john@acme.com",    totalOrders: 14, totalSpend: 124500, lastOrder: "Oct 15, 2024", status: "VIP",    avatar: "AD", color: "#3B5BDB" },
  { id: "c2", company: "Innovate AI",      contact: "Lisa Zhao",      email: "lisa@innovate.ai", totalOrders: 8,  totalSpend: 87200,  lastOrder: "Oct 22, 2024", status: "Active", avatar: "IA", color: "#845EF7" },
  { id: "c3", company: "Nexus Logistics",  contact: "Ben Torres",     email: "ben@nexus.co",     totalOrders: 21, totalSpend: 198400, lastOrder: "Oct 28, 2024", status: "VIP",    avatar: "NL", color: "#F59F00" },
  { id: "c4", company: "Starlight Retail", contact: "Amy Singh",      email: "amy@starlight.com",totalOrders: 5,  totalSpend: 21600,  lastOrder: "Sep 14, 2024", status: "Active", avatar: "SR", color: "#2F9E44" },
  { id: "c5", company: "DataBridge Corp",  contact: "Kai Müller",     email: "kai@databridge.io",totalOrders: 11, totalSpend: 96000,  lastOrder: "Oct 25, 2024", status: "Active", avatar: "DB", color: "#FA5252" },
  { id: "c6", company: "PulseWave Media",  contact: "Nina Cross",     email: "nina@pulse.media", totalOrders: 3,  totalSpend: 14800,  lastOrder: "Aug 30, 2024", status: "Inactive",avatar:"PW", color: "#ADB5BD" },
  { id: "c7", company: "Vantage Systems",  contact: "Ray Okafor",     email: "ray@vantage.net",  totalOrders: 17, totalSpend: 156000, lastOrder: "Oct 27, 2024", status: "VIP",    avatar: "VS", color: "#4DABF7" },
];

// ─────────────────────────────────────────────────────────────────────────────
// ── HELPERS
// ─────────────────────────────────────────────────────────────────────────────
const fmt = (n) =>
  n >= 1000
    ? `$${(n / 1000).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}k`
    : `$${n.toLocaleString()}`;

const fmtFull = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

// ─────────────────────────────────────────────────────────────────────────────
// ── SHARED: Stat Card
// ─────────────────────────────────────────────────────────────────────────────
function SalesStatCard({ icon: Icon, label, value, change, changeType, featured = false }) {
  const changeClass = changeType === "up" ? s.chUp : changeType === "down" ? s.chDown : s.chNeutral;
  return (
    <div className={s.salesStatCard}>
      <div className={`${s.salesStatIconBadge} ${featured ? s.salesStatIconBadgeActive : s.salesStatIconBadgeNeutral}`} aria-hidden="true">
        <Icon className={s.salesStatIcon} strokeWidth={2.2} />
      </div>
      <div>
        <p className={s.salesStatLabel}>{label}</p>
        <p className={s.salesStatValue}>{value}</p>
        {change && (
          <p className={`${s.salesStatChange} ${changeClass}`}>
            {changeType === "up" ? "▲" : changeType === "down" ? "▼" : "●"} {change}
          </p>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── TAB 1: LEAD PIPELINE (KANBAN)
// ─────────────────────────────────────────────────────────────────────────────
function LeadCard({ lead, onDragStart, onStageChange }) {
  const pm = PRIORITY_META[lead.priority];
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!showMenu) return;
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setShowMenu(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showMenu]);

  return (
    <div
      className={s.leadCard}
      draggable
      onDragStart={(e) => onDragStart(e, lead.id)}
      aria-label={`Lead: ${lead.company}`}
    >
      {/* Priority badge */}
      <div className={s.leadTopRow}>
        <span
          className={s.priorityBadge}
          style={{ background: pm.bg, color: pm.color, border: `1px solid ${pm.border}` }}
        >
          {lead.priority}
        </span>
        <div className={s.leadMenuWrap} ref={menuRef}>
          <button
            className={s.leadMenuBtn}
            onClick={() => setShowMenu((o) => !o)}
            aria-label="More options"
          >
            <MoreHorizontal aria-hidden="true" />
          </button>
          {showMenu && (
            <div className={s.leadDropdown}>
              {PIPELINE_COLS.filter((c) => c.id !== lead.stage).map((col) => (
                <button
                  key={col.id}
                  className={s.leadDropItem}
                  onClick={() => { onStageChange(lead.id, col.id); setShowMenu(false); }}
                >
                  Move → {col.label}
                </button>
              ))}
              <hr className={s.leadDropDivider} />
              <button className={`${s.leadDropItem} ${s.leadDropDanger}`}>
                <Trash2 aria-hidden="true" />
                Delete Lead
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Company */}
      <p className={s.leadCompany}>{lead.company}</p>

      {/* Amount */}
      <p className={s.leadAmount}>
        <span className={s.dollarIcon}>$</span>
        {lead.amount.toLocaleString()}
      </p>

      {/* Footer */}
      <div className={s.leadFooter}>
        <span className={s.leadDays}>
          <Clock3 className={s.inlineIcon} aria-hidden="true" />
          {lead.days} day{lead.days !== 1 ? "s" : ""}
        </span>
        <div
          className={s.leadAssignee}
          style={{ background: lead.assigneeColor }}
          title={lead.assignee}
        >
          {lead.assignee}
        </div>
      </div>
    </div>
  );
}

function PipelineTab() {
  const [leads, setLeads] = useState(INITIAL_LEADS);
  const [draggingId, setDraggingId] = useState(null);
  const [showAddLead, setShowAddLead] = useState(false);
  const [newLead, setNewLead] = useState({ company: "", amount: "", priority: "MEDIUM", stage: "prospecting" });

  const handleDragStart = useCallback((e, id) => {
    setDraggingId(id);
    e.dataTransfer.effectAllowed = "move";
  }, []);

  const handleDrop = useCallback((e, stageId) => {
    e.preventDefault();
    if (!draggingId) return;
    setLeads((prev) =>
      prev.map((l) => (l.id === draggingId ? { ...l, stage: stageId } : l))
    );
    setDraggingId(null);
  }, [draggingId]);

  const handleStageChange = useCallback((leadId, newStage) => {
    setLeads((prev) => prev.map((l) => (l.id === leadId ? { ...l, stage: newStage } : l)));
  }, []);

  const handleAddLead = () => {
    if (!newLead.company.trim() || !newLead.amount) return;
    const id = `l${Date.now()}`;
    setLeads((prev) => [...prev, {
      id,
      company: newLead.company.trim(),
      amount: parseFloat(newLead.amount) || 0,
      priority: newLead.priority,
      stage: newLead.stage,
      days: 0,
      assignee: "AS",
      assigneeColor: "#3B5BDB",
    }]);
    setNewLead({ company: "", amount: "", priority: "MEDIUM", stage: "prospecting" });
    setShowAddLead(false);
  };

  // Stats
  const totalPipeline = leads.reduce((a, l) => a + l.amount, 0);
  const wonLeads      = leads.filter((l) => l.stage === "closed_won");
  const totalWon      = wonLeads.reduce((a, l) => a + l.amount, 0);

  return (
    <div>
      {/* Top Stats */}
      <div className={s.pipelineStats}>
        <SalesStatCard icon={CircleDollarSign} label="Pipeline Value"  value={fmtFull(totalPipeline)} change="+14.2%" changeType="up" featured />
        <SalesStatCard icon={CheckCircle2} label="Closed Won"      value={fmtFull(totalWon)}      change="+8.6%"  changeType="up" />
        <SalesStatCard icon={ClipboardList} label="Active Leads"    value={leads.length}            change="+3"     changeType="up" />
        <SalesStatCard icon={Target} label="Win Rate"        value="68%"                     change="+2.1%"  changeType="up" />
      </div>

      {/* Header */}
      <div className={s.pipelineHeader}>
        <div>
          <h2 className={s.pipelineTitle}>Lead Pipeline</h2>
          <p className={s.pipelineSub}>Drag cards between stages to update status.</p>
        </div>
        <button className={s.btnPrimary} onClick={() => setShowAddLead(true)}>+ New Lead</button>
      </div>

      {/* Add Lead Form */}
      {showAddLead && (
        <div className={s.addLeadForm}>
          <div className={s.addLeadGrid}>
            <div className={s.addLeadField}>
              <label className={s.addLeadLabel}>Company Name *</label>
              <input
                className={s.addLeadInput}
                value={newLead.company}
                onChange={(e) => setNewLead((p) => ({ ...p, company: e.target.value }))}
                placeholder="e.g. Acme Corp"
              />
            </div>
            <div className={s.addLeadField}>
              <label className={s.addLeadLabel}>Deal Value ($)</label>
              <input
                type="number"
                className={s.addLeadInput}
                value={newLead.amount}
                onChange={(e) => setNewLead((p) => ({ ...p, amount: e.target.value }))}
                placeholder="e.g. 25000"
              />
            </div>
            <div className={s.addLeadField}>
              <label className={s.addLeadLabel}>Priority</label>
              <select
                className={s.addLeadInput}
                value={newLead.priority}
                onChange={(e) => setNewLead((p) => ({ ...p, priority: e.target.value }))}
              >
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>
            </div>
            <div className={s.addLeadField}>
              <label className={s.addLeadLabel}>Stage</label>
              <select
                className={s.addLeadInput}
                value={newLead.stage}
                onChange={(e) => setNewLead((p) => ({ ...p, stage: e.target.value }))}
              >
                {PIPELINE_COLS.map((c) => (
                  <option key={c.id} value={c.id}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className={s.addLeadActions}>
            <button className={s.btnGhost} onClick={() => setShowAddLead(false)}>Cancel</button>
            <button className={s.btnPrimary} onClick={handleAddLead}>Add Lead</button>
          </div>
        </div>
      )}

      {/* Kanban Board */}
      <div className={s.kanbanBoard}>
        {PIPELINE_COLS.map((col) => {
          const colLeads = leads.filter((l) => l.stage === col.id);
          const colValue = colLeads.reduce((a, l) => a + l.amount, 0);
          return (
            <div
              key={col.id}
              className={s.kanbanCol}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => handleDrop(e, col.id)}
            >
              {/* Column Header */}
              <div className={s.colHeader}>
                <div className={s.colHeaderLeft}>
                  <span className={s.colDot} style={{ background: col.color }} />
                  <span className={s.colLabel}>{col.label}</span>
                  <span className={s.colCount}>{colLeads.length}</span>
                </div>
                <button
                  className={s.colAddBtn}
                  onClick={() => { setNewLead((p) => ({ ...p, stage: col.id })); setShowAddLead(true); }}
                  aria-label={`Add lead to ${col.label}`}
                >
                  +
                </button>
              </div>

              {/* Column Value */}
              <p className={s.colValue}>{fmt(colValue)}</p>

              {/* Cards */}
              <div className={s.colCards}>
                {colLeads.length === 0 ? (
                  <div className={s.colEmpty}>Drop leads here</div>
                ) : (
                  colLeads.map((lead) => (
                    <LeadCard
                      key={lead.id}
                      lead={lead}
                      onDragStart={handleDragStart}
                      onStageChange={handleStageChange}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── TAB 2: SALES ANALYTICS
// ─────────────────────────────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className={s.tooltip}>
      <p className={s.tooltipTitle}>{label}</p>
      {payload.map((e) => (
        <p key={e.name} className={s.tooltipRow} style={{ color: e.color }}>
          {e.name}: <strong>{typeof e.value === "number" && e.value > 999 ? `$${e.value.toLocaleString()}` : e.value}</strong>
        </p>
      ))}
    </div>
  );
};

function SalesAnalyticsTab() {
  return (
    <div>
      {/* KPI Row */}
      <div className={s.analyticsKpiGrid}>
        <SalesStatCard icon={CircleDollarSign} label="Total Revenue (YTD)"  value="$928,000"  change="+18.4%" changeType="up" featured />
        <SalesStatCard icon={ChartNoAxesCombined} label="Avg Deal Size"        value="$32,400"   change="+6.2%"  changeType="up"   />
        <SalesStatCard icon={Clock3} label="Sales Cycle (days)"   value="24d"       change="-3d"    changeType="up"   />
        <SalesStatCard icon={Target} label="Quota Attainment"     value="87%"       change="+5%"    changeType="up"   />
        <SalesStatCard icon={RefreshCcw} label="Churn Rate"           value="4.2%"      change="+0.3%"  changeType="down" />
        <SalesStatCard icon={UserRoundPlus} label="New MQLs"             value="142"       change="+21"    changeType="up"   />
      </div>

      {/* Charts Row 1 */}
      <div className={s.analyticsRow}>
        {/* Revenue vs Target */}
        <div className={s.analyticsCard} style={{ flex: 2 }}>
          <h3 className={s.analyticsCardTitle}>Monthly Revenue vs Target</h3>
          <p className={s.analyticsCardSub}>6-month performance comparison</p>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={MONTHLY_REVENUE} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="gradSalesRev" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B5BDB" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#3B5BDB" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F3F5" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#ADB5BD" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#ADB5BD" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v / 1000}k`} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#3B5BDB" strokeWidth={2.5} fill="url(#gradSalesRev)" dot={false} />
              <Area type="monotone" dataKey="target"  name="Target"  stroke="#CED4DA" strokeWidth={2} fill="none" strokeDasharray="4 4" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Win/Loss Donut */}
        <div className={s.analyticsCard} style={{ flex: 1, minWidth: 220 }}>
          <h3 className={s.analyticsCardTitle}>Win/Loss Ratio</h3>
          <p className={s.analyticsCardSub}>Last 12 months</p>
          <div style={{ display: "flex", justifyContent: "center", marginTop: 8 }}>
            <PieChart width={160} height={160}>
              <Pie data={WIN_LOSS_DATA} cx={75} cy={75} innerRadius={50} outerRadius={72} paddingAngle={3} dataKey="value">
                {WIN_LOSS_DATA.map((e, i) => <Cell key={i} fill={e.fill} />)}
              </Pie>
            </PieChart>
          </div>
          <div className={s.winLossLegend}>
            {WIN_LOSS_DATA.map((e) => (
              <div key={e.name} className={s.winLossItem}>
                <span className={s.winLossDot} style={{ background: e.fill }} />
                <span className={s.winLossLabel}>{e.name}</span>
                <span className={s.winLossVal}>{e.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className={s.analyticsRow}>
        {/* Pipeline by Stage */}
        <div className={s.analyticsCard} style={{ flex: 1 }}>
          <h3 className={s.analyticsCardTitle}>Pipeline Value by Stage</h3>
          <p className={s.analyticsCardSub}>Current deals in each stage</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={PIPELINE_VALUE_BY_STAGE} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F3F5" />
              <XAxis dataKey="stage" tick={{ fontSize: 10, fill: "#ADB5BD" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#ADB5BD" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v / 1000}k`} />
              <Tooltip formatter={(v) => [`$${v.toLocaleString()}`, "Value"]} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {PIPELINE_VALUE_BY_STAGE.map((e, i) => <Cell key={i} fill={e.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Top Reps */}
        <div className={s.analyticsCard} style={{ flex: 1 }}>
          <h3 className={s.analyticsCardTitle}>Top Sales Reps</h3>
          <p className={s.analyticsCardSub}>By quota attainment this quarter</p>
          <div className={s.topRepsList}>
            {TOP_REPS.map((rep, i) => (
              <div key={rep.name} className={s.topRepRow}>
                <span className={s.topRepRank}>#{i + 1}</span>
                <div className={s.topRepAvatar} style={{ background: rep.color }}>{rep.avatar}</div>
                <div className={s.topRepInfo}>
                  <p className={s.topRepName}>{rep.name}</p>
                  <div className={s.topRepBar}>
                    <div className={s.topRepBarFill} style={{ width: `${rep.quota}%`, background: rep.color }} />
                  </div>
                </div>
                <div className={s.topRepStats}>
                  <span className={s.topRepRevenue}>{fmt(rep.revenue)}</span>
                  <span className={s.topRepDeals}>{rep.deals} deals</span>
                </div>
                <span className={s.topRepQuota} style={{ color: rep.color }}>{rep.quota}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── TAB 3: PRODUCT CATALOG
// ─────────────────────────────────────────────────────────────────────────────
function ProductCatalogTab() {
  const [products, setProducts] = useState(INITIAL_PRODUCTS);
  const [search, setSearch]     = useState("");
  const [category, setCategory] = useState("All");
  const [showAdd, setShowAdd]   = useState(false);
  const [newProduct, setNewProduct] = useState({ name: "", category: "Software", price: "", sku: "", description: "" });

  const filtered = useMemo(() =>
    products.filter((p) => {
      const matchCat = category === "All" || p.category === category;
      const matchSearch = !search || p.name.toLowerCase().includes(search.toLowerCase()) || p.sku.toLowerCase().includes(search.toLowerCase());
      return matchCat && matchSearch;
    }),
    [products, category, search]
  );

  const handleAddProduct = () => {
    if (!newProduct.name.trim() || !newProduct.price) return;
    setProducts((prev) => [...prev, {
      id: `p${Date.now()}`,
      name: newProduct.name.trim(),
      category: newProduct.category,
      price: parseFloat(newProduct.price) || 0,
      sku: newProduct.sku.trim() || `SKU-${Date.now()}`,
      stock: "∞",
      status: "Active",
      description: newProduct.description,
    }]);
    setNewProduct({ name: "", category: "Software", price: "", sku: "", description: "" });
    setShowAdd(false);
  };

  const statusClass = (s) => ({
    Active: styles => styles.prodStatusActive,
    Draft: styles => styles.prodStatusDraft,
    "Low Stock": styles => styles.prodStatusLow,
  }[s] || (() => ""));

  return (
    <div>
      {/* Toolbar */}
      <div className={s.catalogToolbar}>
        <div className={s.searchWrap}>
          <Search className={s.searchIcon} aria-hidden="true" />
          <input
            className={s.searchInput}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products or SKUs..."
          />
        </div>
        <div className={s.catTabs}>
          {PRODUCT_CATEGORIES.map((c) => (
            <button
              key={c}
              className={`${s.catTab} ${category === c ? s.catTabActive : ""}`}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </div>
        <button className={s.btnPrimary} onClick={() => setShowAdd(true)}>+ Add Product</button>
      </div>

      {/* Add Product Form */}
      {showAdd && (
        <div className={s.addLeadForm}>
          <div className={s.addLeadGrid} style={{ gridTemplateColumns: "1fr 1fr 1fr 1fr" }}>
            <div className={s.addLeadField}>
              <label className={s.addLeadLabel}>Product Name *</label>
              <input className={s.addLeadInput} value={newProduct.name} onChange={(e) => setNewProduct((p) => ({ ...p, name: e.target.value }))} placeholder="Product name" />
            </div>
            <div className={s.addLeadField}>
              <label className={s.addLeadLabel}>Category</label>
              <select className={s.addLeadInput} value={newProduct.category} onChange={(e) => setNewProduct((p) => ({ ...p, category: e.target.value }))}>
                {PRODUCT_CATEGORIES.filter((c) => c !== "All").map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className={s.addLeadField}>
              <label className={s.addLeadLabel}>Price ($) *</label>
              <input type="number" className={s.addLeadInput} value={newProduct.price} onChange={(e) => setNewProduct((p) => ({ ...p, price: e.target.value }))} placeholder="0.00" />
            </div>
            <div className={s.addLeadField}>
              <label className={s.addLeadLabel}>SKU</label>
              <input className={s.addLeadInput} value={newProduct.sku} onChange={(e) => setNewProduct((p) => ({ ...p, sku: e.target.value }))} placeholder="e.g. SW-001" />
            </div>
          </div>
          <div className={s.addLeadActions}>
            <button className={s.btnGhost} onClick={() => setShowAdd(false)}>Cancel</button>
            <button className={s.btnPrimary} onClick={handleAddProduct}>Add Product</button>
          </div>
        </div>
      )}

      {/* Product Grid */}
      <div className={s.productGrid}>
        {filtered.map((prod) => {
          const statusMeta = {
            Active:     { cls: s.prodStatusActive, color: "#2F9E44", bg: "#EBFBEE" },
            Draft:      { cls: s.prodStatusDraft,  color: "#6C757D", bg: "#F1F3F5" },
            "Low Stock":{ cls: s.prodStatusLow,    color: "#E67700", bg: "#FFF3BF" },
          }[prod.status] || { color: "#6C757D", bg: "#F1F3F5" };
          const CategoryIcon = { Software: Laptop, Hardware: HardDrive, Cloud, Services: Wrench }[prod.category] || Package;
          return (
            <div key={prod.id} className={s.productCard}>
              <div className={s.productCardTop}>
                <div className={s.productIcon} aria-hidden="true">
                  <CategoryIcon className={s.productIconSvg} />
                </div>
                <span className={s.productStatus} style={{ background: statusMeta.bg, color: statusMeta.color }}>
                  {prod.status}
                </span>
              </div>
              <p className={s.productName}>{prod.name}</p>
              <p className={s.productDesc}>{prod.description}</p>
              <div className={s.productMeta}>
                <span className={s.productCat}>{prod.category}</span>
                <span className={s.productSku}>{prod.sku}</span>
              </div>
              <div className={s.productFooter}>
                <span className={s.productPrice}>{fmtFull(prod.price)}</span>
                <div className={s.productActions}>
                  <button className={s.prodActionBtn} aria-label="Edit"><Pencil aria-hidden="true" /></button>
                  <button className={s.prodActionBtn} aria-label="More"><MoreHorizontal aria-hidden="true" /></button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className={s.emptyState}>
          <Package className={s.emptyIcon} aria-hidden="true" />
          <p className={s.emptyTitle}>No products found</p>
          <p className={s.emptySub}>Try adjusting your filters.</p>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── TAB 4: CUSTOMERS & ORDERS
// ─────────────────────────────────────────────────────────────────────────────
function CustomersTab() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");

  const statusFilters = ["All", "VIP", "Active", "Inactive"];

  const filtered = useMemo(() =>
    CUSTOMERS.filter((c) => {
      const matchSearch = !search || c.company.toLowerCase().includes(search.toLowerCase()) || c.contact.toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === "All" || c.status === statusFilter;
      return matchSearch && matchStatus;
    }),
    [search, statusFilter]
  );

  const statusMeta = {
    VIP:      { bg: "#FFF3BF", color: "#E67700" },
    Active:   { bg: "#EBFBEE", color: "#2F9E44" },
    Inactive: { bg: "#F1F3F5", color: "#6C757D" },
  };

  return (
    <div>
      {/* Stats */}
      <div className={s.pipelineStats}>
        <SalesStatCard icon={Users} label="Total Customers" value={CUSTOMERS.length}           change="+3 this month"  changeType="up" featured />
        <SalesStatCard icon={Crown} label="VIP Accounts"    value={CUSTOMERS.filter(c=>c.status==="VIP").length} change="High value" changeType="up" />
        <SalesStatCard icon={CircleDollarSign} label="Total Revenue"   value={fmtFull(CUSTOMERS.reduce((a,c)=>a+c.totalSpend,0))} change="+12.4%" changeType="up" />
        <SalesStatCard icon={ShoppingCart} label="Total Orders"    value={CUSTOMERS.reduce((a,c)=>a+c.totalOrders,0)}  change="+18 this month" changeType="up" />
      </div>

      {/* Toolbar */}
      <div className={s.catalogToolbar}>
        <div className={s.searchWrap}>
          <Search className={s.searchIcon} aria-hidden="true" />
          <input
            className={s.searchInput}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search companies or contacts..."
          />
        </div>
        <div className={s.catTabs}>
          {statusFilters.map((f) => (
            <button
              key={f}
              className={`${s.catTab} ${statusFilter === f ? s.catTabActive : ""}`}
              onClick={() => setStatusFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
        <button className={s.btnOutline}>
          <Download className={s.btnIcon} aria-hidden="true" />
          Export
        </button>
      </div>

      {/* Table */}
      <div className={s.customersTable}>
        <table className={s.custTable}>
          <thead className={s.custThead}>
            <tr>
              <th className={s.custTh}>Company</th>
              <th className={s.custTh}>Contact</th>
              <th className={s.custTh}>Total Orders</th>
              <th className={s.custTh}>Total Spend</th>
              <th className={s.custTh}>Last Order</th>
              <th className={s.custTh}>Status</th>
              <th className={s.custTh} style={{ textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((cust) => {
              const sm = statusMeta[cust.status] || statusMeta.Active;
              return (
                <tr key={cust.id} className={s.custTr}>
                  <td className={s.custTd}>
                    <div className={s.custCompanyCell}>
                      <div className={s.custAvatar} style={{ background: cust.color }}>{cust.avatar}</div>
                      <div>
                        <p className={s.custCompanyName}>{cust.company}</p>
                        <p className={s.custEmail}>{cust.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className={s.custTd}><span className={s.custContact}>{cust.contact}</span></td>
                  <td className={s.custTd}><span className={s.custOrders}>{cust.totalOrders} orders</span></td>
                  <td className={s.custTd}><span className={s.custSpend}>{fmtFull(cust.totalSpend)}</span></td>
                  <td className={s.custTd}><span className={s.custDate}>{cust.lastOrder}</span></td>
                  <td className={s.custTd}>
                    <span className={s.custStatus} style={{ background: sm.bg, color: sm.color }}>
                      {cust.status}
                    </span>
                  </td>
                  <td className={s.custTd} style={{ textAlign: "right" }}>
                    <div className={s.custActions}>
                      <button className={s.custActionBtn} aria-label="View"><Eye aria-hidden="true" /></button>
                      <button className={s.custActionBtn} aria-label="Message"><Mail aria-hidden="true" /></button>
                      <button className={s.custActionBtn} aria-label="More"><MoreHorizontal aria-hidden="true" /></button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className={s.emptyState}>
            <Users className={s.emptyIcon} aria-hidden="true" />
            <p className={s.emptyTitle}>No customers found</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────
const TABS = [
  { id: "pipeline",  label: "Lead Pipeline"     },
  { id: "analytics", label: "Sales Analytics"   },
  { id: "catalog",   label: "Product Catalog"   },
  { id: "customers", label: "Customers & Orders" },
];

export default function SalesPage() {
  const [activeNav, setActiveNav] = useState("sales");
  const [activeTab, setActiveTab] = useState("pipeline");
  const navigate = useNavigate();

  return (
    <div className={shell.appShell}>
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />

      <div className={shell.mainArea}>
        <Header breadcrumbs={["Prime ERP", "Sales", activeTab === "pipeline" ? "Pipeline" : TABS.find(t => t.id === activeTab)?.label]} />

        <main className={s.page}>
          {/* Page Header */}
          <header className={s.pageHeader}>
            <div>
              <h1 className={s.pageTitle}>Sales & CRM</h1>
              <p className={s.pageSub}>Manage your leads, pipeline, catalog, and customer relationships.</p>
            </div>
            <div className={s.headerActions}>
              <button className={s.btnOutline} onClick={() => setActiveTab("catalog")}>
                <ShoppingCart className={s.btnIcon} aria-hidden="true" />
                Product Catalog
              </button>
              <button className={s.btnPrimary} onClick={() => setActiveTab("pipeline")}>
                <Plus className={s.btnIcon} aria-hidden="true" />
                New Lead
              </button>
            </div>
          </header>

          {/* Tab Bar */}
          <div className={s.tabBar} role="tablist">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeTab === tab.id}
                className={`${s.tabBtn} ${activeTab === tab.id ? s.tabBtnActive : ""}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
            <div className={s.tabBarRight}>
              <button className={s.filterBtn}>
                <SlidersHorizontal className={s.btnIcon} aria-hidden="true" />
                Filter
              </button>
            </div>
          </div>

          {/* Tab Content */}
          <div key={activeTab} className={s.tabContent}>
            {activeTab === "pipeline"  && <PipelineTab />}
            {activeTab === "analytics" && <SalesAnalyticsTab />}
            {activeTab === "catalog"   && <ProductCatalogTab />}
            {activeTab === "customers" && <CustomersTab />}
          </div>
        </main>

        {/* Footer */}
        <footer className={s.footer}>
          <span>© 2026 Prime ERP Systems. All rights reserved.</span>
          <div className={s.footerRight}>
            <a href="#" className={s.footerLink}>Privacy Policy</a>
            <a href="#" className={s.footerLink}>Terms of Service</a>
            <span className={s.statusDot}>● System Status: Operational</span>
            <span>v2.4.0-stable</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
