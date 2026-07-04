import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Hexagon,
  Sparkles,
  TrendingUp,
  DollarSign,
  Users,
  ShoppingCart,
  Boxes,
  Activity,
  UserCheck,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  FileSpreadsheet,
  Headphones,
  ArrowRight
} from "lucide-react";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend
} from "recharts";

// Real mock dataset for Recharts
const monthlyLedgerData = [
  { month: "Jan", Income: 85000, Expenses: 58000, CashFlow: 27000 },
  { month: "Feb", Income: 92000, Expenses: 61000, CashFlow: 31000 },
  { month: "Mar", Income: 110000, Expenses: 64000, CashFlow: 46000 },
  { month: "Apr", Income: 105000, Expenses: 68000, CashFlow: 37000 },
  { month: "May", Income: 125000, Expenses: 72000, CashFlow: 53000 },
  { month: "Jun", Income: 140000, Expenses: 75000, CashFlow: 65000 }
];

const inventoryProductData = [
  { item: "Model X-8", Stock: 85, SafetyLevel: 30 },
  { item: "Core Chip", Stock: 142, SafetyLevel: 50 },
  { item: "Sensor Array", Stock: 12, SafetyLevel: 40 }, // Under Stock
  { item: "Cable Harness", Stock: 210, SafetyLevel: 80 },
  { item: "Power Block", Stock: 44, SafetyLevel: 25 }
];

const csatDistributionData = [
  { name: "Excellent (5★)", value: 65, color: "#10B981" },
  { name: "Good (4★)", value: 24, color: "#3B82F6" },
  { name: "Average (3★)", value: 8, color: "#F59E0B" },
  { name: "Poor (1-2★)", value: 3, color: "#EF4444" }
];

export default function DashboardPreview() {
  const [activeTab, setActiveTab] = useState("ledger");
  const [aiSuggestions, setAiSuggestions] = useState([
    {
      id: "sug-1",
      module: "Inventory",
      type: "Warning",
      text: "Sensor Array stock is currently at 12 units (Safety Threshold: 40). Stockout likely in 4 days based on orders.",
      actionText: "Auto-Reorder 150 units",
      isResolved: false
    },
    {
      id: "sug-2",
      module: "Finance",
      type: "Optimize",
      text: "Identified cash savings opportunity of $2,400 monthly by consolidating redundant Slack & Zoom developer workspaces.",
      actionText: "Review Workspace Billing",
      isResolved: false
    },
    {
      id: "sug-3",
      module: "Support",
      type: "Automation",
      text: "SLA response bottleneck detected in European region tickets between 2PM and 4PM local times.",
      actionText: "Deploy Smart Bot",
      isResolved: false
    }
  ]);

  const handleResolveSuggestion = (id) => {
    setAiSuggestions((prev) =>
      prev.map((sug) => (sug.id === id ? { ...sug, isResolved: true } : sug))
    );
  };

  return (
    <section
      id="analytics"
      className="py-24 md:py-32 bg-transparent text-slate-900 relative overflow-hidden"
    >
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-blue-50/10 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-16">
        
        {/* Section Header */}
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-600 border border-emerald-100">
            <Activity className="w-3.5 h-3.5" />
            Live System Sandbox
          </span>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 font-sans">
            Real-Time Prime Terminal
          </h2>
          <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto">
            Explore the raw processing horsepower. Click the controls to switch between ledger charts, supply chain telemetry, and customer intelligence modules.
          </p>
        </div>

        {/* Dashboard Frame */}
        <div className="rounded-3xl bg-white/70 border border-white/50 backdrop-blur-xl shadow-[0_32px_64px_-16px_rgba(0,0,0,0.08)] p-6 md:p-8 space-y-8 text-left relative text-slate-800">
          
          {/* Top Panel Brand */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl">
                <Hexagon className="w-6 h-6 text-white fill-white/10" />
              </div>
              <div>
                <h3 className="text-lg font-sans font-extrabold text-slate-900">HQ Enterprise Console</h3>
                <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest">Global Corporate Deployment (ID: PRIME-4A7)</span>
              </div>
            </div>

            {/* Selector Tabs */}
            <div className="flex flex-wrap gap-2">
              {[
                { id: "ledger", label: "Financial Ledger", icon: DollarSign },
                { id: "supply", label: "Smart Warehouse", icon: Boxes },
                { id: "workplace", label: "Workplace & Service", icon: UserCheck }
              ].map((tab) => {
                const TabIcon = tab.icon;
                const isSelected = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    id={`dash-tab-${tab.id}`}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                      isSelected
                        ? "bg-blue-600 text-white border-blue-500 shadow-lg shadow-blue-500/15"
                        : "bg-white/50 border border-slate-200/60 text-slate-600 hover:bg-slate-50/80 hover:text-slate-900"
                    }`}
                  >
                    <TabIcon className="w-3.5 h-3.5" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Master 12-Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            
            {/* LEFT 8-COLUMNS: Active Tab Visualizer */}
            <div className="lg:col-span-8 space-y-6">
              
              <AnimatePresence mode="wait">
                {activeTab === "ledger" && (
                  <motion.div
                    key="ledger"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-6"
                  >
                    {/* Metrics row */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">Total Gross Revenue</div>
                        <div className="text-xl font-black text-slate-900 mt-1">$659,000</div>
                        <span className="text-[10px] text-emerald-600 font-bold flex items-center gap-1 mt-1">
                          <TrendingUp className="w-3 h-3" /> +16.4% MoM
                        </span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">Consolidated Expenses</div>
                        <div className="text-xl font-black text-slate-900 mt-1">$398,000</div>
                        <span className="text-[10px] text-slate-500 font-bold block mt-1">Within baseline limits</span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">Cash Profit Margin</div>
                        <div className="text-xl font-black text-slate-900 mt-1">39.6%</div>
                        <span className="text-[10px] text-emerald-600 font-bold flex items-center gap-1 mt-1">
                          <TrendingUp className="w-3 h-3" /> +2.8% Yield
                        </span>
                      </div>
                    </div>

                    {/* Ledger Chart */}
                    <div className="bg-white/80 p-5 rounded-2xl border border-slate-200/60 shadow-sm">
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <h4 className="text-sm font-bold text-slate-900">Monthly Cash Flow & Income Ledger</h4>
                          <p className="text-[10px] text-slate-500">Includes auto-reconciled tax bookings</p>
                        </div>
                        <div className="flex gap-4 text-[10px] font-mono">
                          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-blue-500" /> Income</span>
                          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-red-400" /> Expenses</span>
                          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-emerald-400" /> Net Runway</span>
                        </div>
                      </div>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={monthlyLedgerData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                            <defs>
                              <linearGradient id="colorIncome" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.2}/>
                                <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                              </linearGradient>
                              <linearGradient id="colorCash" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#10B981" stopOpacity={0.2}/>
                                <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <XAxis dataKey="month" stroke="#64748b" fontSize={10} tickLine={false} />
                            <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                            <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "12px", boxShadow: "0 4px 12px rgba(0,0,0,0.05)", color: "#1e293b", fontSize: "11px" }} />
                            <Area type="monotone" dataKey="Income" stroke="#3B82F6" strokeWidth={2} fillOpacity={1} fill="url(#colorIncome)" />
                            <Area type="monotone" dataKey="CashFlow" stroke="#10B981" strokeWidth={2} fillOpacity={1} fill="url(#colorCash)" />
                            <Line type="monotone" dataKey="Expenses" stroke="#EF4444" strokeWidth={1.5} dot={{ r: 2 }} />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </motion.div>
                )}

                {activeTab === "supply" && (
                  <motion.div
                    key="supply"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-6"
                  >
                    {/* Supply metrics */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">Total SKUs Tracked</div>
                        <div className="text-xl font-black text-slate-900 mt-1">14,892</div>
                        <span className="text-[10px] text-slate-500 font-bold block mt-1">Across 4 regional hubs</span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">Out of Stock Alerts</div>
                        <div className="text-xl font-black text-slate-900 mt-1 flex items-center gap-2">
                          1 <span className="text-xs bg-amber-50 text-amber-600 px-2 py-0.5 rounded border border-amber-100 font-semibold">Low Stock</span>
                        </div>
                        <span className="text-[10px] text-slate-500 font-bold block mt-1">Auto-reorder script queued</span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">Fulfillment Speeds</div>
                        <div className="text-xl font-black text-slate-900 mt-1">18.4 Hours</div>
                        <span className="text-[10px] text-emerald-600 font-bold flex items-center gap-1 mt-1">
                          <TrendingUp className="w-3 h-3" /> -12% Delay reduction
                        </span>
                      </div>
                    </div>

                    {/* Inventory bar chart */}
                    <div className="bg-white/80 p-5 rounded-2xl border border-slate-200/60 shadow-sm">
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <h4 className="text-sm font-bold text-slate-900">Smart Warehouse Catalog Status</h4>
                          <p className="text-[10px] text-slate-500">Highlights stock levels against critical security limits</p>
                        </div>
                        <span className="text-[10px] font-mono text-cyan-600 bg-cyan-50 px-2 py-0.5 rounded border border-cyan-100">Live Telemetry</span>
                      </div>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={inventoryProductData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <XAxis dataKey="item" stroke="#64748b" fontSize={10} tickLine={false} />
                            <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                            <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "12px", boxShadow: "0 4px 12px rgba(0,0,0,0.05)", color: "#1e293b", fontSize: "11px" }} />
                            <Legend wrapperStyle={{ fontSize: "10px" }} />
                            <Bar dataKey="Stock" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="SafetyLevel" fill="#EF4444" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </motion.div>
                )}

                {activeTab === "workplace" && (
                  <motion.div
                    key="workplace"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-6"
                  >
                    {/* HR & Support metrics */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">FTE Shift Attendance</div>
                        <div className="text-xl font-black text-slate-900 mt-1">98.4%</div>
                        <span className="text-[10px] text-emerald-600 font-bold flex items-center gap-1 mt-1">
                          <CheckCircle2 className="w-3 h-3" /> Optimum staffing levels
                        </span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">Open Support Tickets</div>
                        <div className="text-xl font-black text-slate-900 mt-1">14 Tickets</div>
                        <span className="text-[10px] text-slate-500 font-bold block mt-1">All SLA boundaries stable</span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/60">
                        <div className="text-[10px] text-slate-500 uppercase font-mono font-bold">Mean Resolution Time</div>
                        <div className="text-xl font-black text-slate-900 mt-1">4.2 Minutes</div>
                        <span className="text-[10px] text-cyan-600 font-bold block mt-1">84% Auto-resolved by bot</span>
                      </div>
                    </div>

                    {/* Support and Satisfaction Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                      
                      {/* Ticket queue */}
                      <div className="md:col-span-7 bg-white/80 p-5 rounded-2xl border border-slate-200/60 shadow-sm">
                        <h4 className="text-sm font-bold text-slate-900 mb-3">Live Service Queue Analytics</h4>
                        <div className="space-y-3">
                          {[
                            { id: "T-809", user: "Michael G.", subject: "Multi-entity accounting mapping error", status: "In-Progress", color: "text-blue-600" },
                            { id: "T-810", user: "Acme Corp Ltd", subject: "SAML SSO redirection bottleneck", status: "Review", color: "text-amber-600" },
                            { id: "T-811", user: "Sarah L.", subject: "Automatic PDF ledger scheduler timing", status: "Closed by AI", color: "text-emerald-600" }
                          ].map((ticket) => (
                            <div key={ticket.id} className="flex items-center justify-between border-b border-slate-100 pb-2.5 last:border-0 last:pb-0">
                              <div className="text-left">
                                <div className="text-xs font-bold text-slate-700">{ticket.subject}</div>
                                <div className="text-[9px] text-slate-400 font-mono mt-0.5">{ticket.id} • Assigned to {ticket.user}</div>
                              </div>
                              <span className={`text-[10px] font-mono font-semibold ${ticket.color}`}>{ticket.status}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Satisfaction Pie Chart */}
                      <div className="md:col-span-5 bg-white/80 p-5 rounded-2xl border border-slate-200/60 shadow-sm flex flex-col justify-between">
                        <h4 className="text-sm font-bold text-slate-900 mb-2">CSAT Distribution</h4>
                        <div className="h-44 relative flex items-center justify-center">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={csatDistributionData}
                                cx="50%"
                                cy="50%"
                                innerRadius={45}
                                outerRadius={60}
                                paddingAngle={5}
                                dataKey="value"
                              >
                                {csatDistributionData.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                              </Pie>
                              <Tooltip />
                            </PieChart>
                          </ResponsiveContainer>
                          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                            <span className="text-base font-extrabold text-slate-900">4.9/5</span>
                            <span className="text-[8px] text-slate-400 font-semibold uppercase">CSAT Avg</span>
                          </div>
                        </div>
                      </div>

                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

            </div>

            {/* RIGHT 4-COLUMNS: Intelligent AI Suggestion Hub */}
            <div className="lg:col-span-4 space-y-4">
              
              <div className="bg-white/80 rounded-2xl p-5 border border-slate-200/80 shadow-[0_12px_24px_rgba(0,0,0,0.03)] relative backdrop-blur-xl">
                
                {/* Header info */}
                <div className="flex items-center gap-2 mb-4">
                  <div className="p-1.5 rounded-lg bg-blue-50 text-blue-600">
                    <Brain className="w-4 h-4 animate-pulse" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold font-mono tracking-wider text-slate-700">AI COGNITIVE ACTIONS</h4>
                    <span className="text-[9px] text-slate-400 font-medium">Real-time continuous audit</span>
                  </div>
                </div>

                {/* Suggestions Stack */}
                <div className="space-y-3">
                  <AnimatePresence>
                    {aiSuggestions.map((sug) => (
                      <motion.div
                        key={sug.id}
                        initial={{ opacity: 1 }}
                        exit={{ opacity: 0, height: 0, scale: 0.95 }}
                        transition={{ duration: 0.25 }}
                        className={`p-3.5 rounded-xl border relative text-left transition-all ${
                          sug.isResolved
                            ? "bg-slate-50/50 border-slate-100 opacity-50 text-slate-400"
                            : "bg-slate-50 border-slate-100 hover:border-slate-200/80 hover:bg-slate-100/50"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className={`text-[8px] font-mono px-2 py-0.5 rounded border ${
                            sug.type === "Warning"
                              ? "bg-red-50 text-red-600 border-red-100"
                              : sug.type === "Optimize"
                              ? "bg-blue-50 text-blue-600 border-blue-100"
                              : "bg-cyan-50 text-cyan-600 border-cyan-100"
                          }`}>
                            {sug.module}: {sug.type}
                          </span>
                          {sug.isResolved && (
                            <span className="text-[8px] text-emerald-600 font-mono font-bold flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> RESOLVED
                            </span>
                          )}
                        </div>

                        <p className="text-[10px] text-slate-600 leading-relaxed font-sans">
                          {sug.text}
                        </p>

                        {!sug.isResolved && (
                          <button
                            id={`btn-resolve-sug-${sug.id}`}
                            onClick={() => handleResolveSuggestion(sug.id)}
                            className="mt-3 w-full py-1.5 bg-blue-600 hover:bg-blue-500 text-[10px] font-bold text-white rounded-lg flex items-center justify-center gap-1 cursor-pointer transition-colors"
                          >
                            <span>{sug.actionText}</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>

                {/* Footnote */}
                <div className="mt-4 text-center text-[10px] text-slate-400 font-mono flex items-center justify-center gap-1">
                  <Sparkles className="w-3 h-3 text-cyan-600" />
                  Audit ledger active. Last audit tick: 1s ago.
                </div>

              </div>

            </div>

          </div>

        </div>
      </div>
    </section>
  );
}



