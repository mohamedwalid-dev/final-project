import React, { useState } from "react";
import { motion } from "motion/react";
import {
  Brain,
  Sparkles,
  ArrowRight,
  Play,
  TrendingUp,
  DollarSign,
  Users,
  Activity,
  Bell,
  Send,
  CheckCircle2,
  Cpu,
  ChevronRight,
  ShieldCheck,
  Globe
} from "lucide-react";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip
} from "recharts";

const miniRevenueData = [
  { name: "Jan", revenue: 42000 },
  { name: "Feb", revenue: 51000 },
  { name: "Mar", revenue: 64000 },
  { name: "Apr", revenue: 78000 },
  { name: "May", revenue: 95000 },
  { name: "Jun", revenue: 110000 }
];

const miniSalesData = [
  { name: "Lead", value: 100 },
  { name: "Contact", value: 80 },
  { name: "Demo", value: 50 },
  { name: "Quote", value: 30 },
  { name: "Closed", value: 18 }
];

export default function Hero() {
  const [chatMessages, setChatMessages] = useState([
    { sender: "assistant", text: "Hello! I am your Enterprise AI Copilot. How can I assist you with your business operations today?" },
    { sender: "user", text: "Verify last month's cash flow anomalies." },
    { sender: "assistant", text: "Analyzing ledger data... Found 1 anomaly: a duplicate invoice draft (#INV-2026-94) from Supplier ACME Corp for $12,450. Would you like me to flag it?" }
  ]);
  const [chatInput, setChatInput] = useState("");

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = chatInput;
    setChatMessages((prev) => [...prev, { sender: "user", text: userMsg }]);
    setChatInput("");

    // Simulate AI response
    setTimeout(() => {
      let reply = "I am processing your query across Prime modules. ";
      if (userMsg.toLowerCase().includes("revenue") || userMsg.toLowerCase().includes("sales")) {
        reply = "Our real-time sales ledger reports Q2 revenue is pacing 24% ahead of schedule at $110,000, led by our enterprise SaaS modules.";
      } else if (userMsg.toLowerCase().includes("inventory") || userMsg.toLowerCase().includes("stock")) {
        reply = "Inventory levels are stable. I have automatically drafted a purchase order for 250 units of model X-8 to avoid a stockout in August.";
      } else if (userMsg.toLowerCase().includes("invoice") || userMsg.toLowerCase().includes("pay")) {
        reply = "Ledgers verified. All scheduled payroll expenses have been successfully queued for July 15, totaling $82,400 across 34 employees.";
      } else {
        reply = "Query parsed. Generating custom dashboard pivot charts. I've scheduled an email containing the executive summary to your inbox.";
      }
      setChatMessages((prev) => [...prev, { sender: "assistant", text: reply }]);
    }, 1000);
  };

  return (
    <section
      id="home"
      className="relative pt-32 pb-24 md:pt-40 md:pb-32 overflow-hidden bg-transparent text-slate-900"
    >
      {/* Background Gradients & Effects */}
      <div className="absolute inset-0 z-0">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-100/30 rounded-full blur-3xl" />
        <div className="absolute bottom-1/3 right-1/4 w-96 h-96 bg-indigo-100/30 rounded-full blur-3xl" />
        <div className="absolute top-10 right-10 w-72 h-72 bg-cyan-100/30 rounded-full blur-3xl animate-pulse" />
        {/* Subtle grid pattern overlay */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#e2e8f080_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f080_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-35" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          
          {/* LEFT: Text Content & Badges */}
          <div className="lg:col-span-5 text-left space-y-8">
            
            {/* Badges */}
            <div className="flex flex-wrap gap-2.5">
              <motion.span
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100"
              >
                <Cpu className="w-3.5 h-3.5" />
                AI Powered
              </motion.span>
              <motion.span
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.1 }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-600 border border-indigo-100"
              >
                <Globe className="w-3.5 h-3.5" />
                Cloud Native
              </motion.span>
              <motion.span
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-cyan-50 text-cyan-600 border border-cyan-100"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                Enterprise Ready
              </motion.span>
            </div>

            {/* Headline */}
            <motion.div
              initial={{ opacity: 0, y: 25 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="space-y-4"
            >
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-sans font-extrabold tracking-tight leading-tight text-slate-900">
                Welcome to{" "}
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">
                  Prime AI-Powered ERP
                </span>
              </h1>
              <p className="text-base sm:text-lg text-slate-600 font-sans leading-relaxed">
                Prime helps businesses automate Finance, HR, Sales, Inventory, and Customer Support using Artificial Intelligence.
              </p>
            </motion.div>

            {/* Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="flex flex-col sm:flex-row gap-4 pt-2"
            >
              <button
                id="hero-btn-login"
                onClick={() => window.location.href = "/login"}
                className="relative px-8 py-4 rounded-xl text-base font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-lg shadow-blue-500/25 hover:shadow-xl hover:shadow-blue-500/35 active:scale-98 cursor-pointer flex items-center justify-center gap-2 group overflow-hidden sm:w-auto"
              >
                <span className="relative z-10 flex items-center gap-2">
                  Login Now
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </span>
                <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              </button>
            </motion.div>

            {/* Micro value props list */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="grid grid-cols-2 gap-x-4 gap-y-2 pt-4 border-t border-slate-200"
            >
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>No Subscription Required</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>Completely Free ERP Platform</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>Free Forever</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>Access Your Dashboard Instantly</span>
              </div>
            </motion.div>

          </div>

          {/* RIGHT: High-Fidelity Dashboard Preview Panel */}
          <div className="lg:col-span-7 relative">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 30 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ duration: 0.7, ease: "easeOut" }}
              className="relative rounded-3xl bg-white/70 border border-white/50 p-5 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.10)] backdrop-blur-xl overflow-hidden text-slate-800"
            >
              {/* Outer decorative gradient glow */}
              <div className="absolute -top-10 -right-10 w-40 h-40 bg-blue-100/40 rounded-full blur-3xl pointer-events-none" />

              {/* Dashboard Header Bar */}
              <div className="flex items-center justify-between border-b border-slate-200/60 pb-4 mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-yellow-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                  <span className="text-xs font-mono text-slate-400 ml-2">https://portal.prime.enterprise/dashboard</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <Bell className="w-4 h-4 text-slate-500 hover:text-slate-700 cursor-pointer" />
                    <div className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-blue-600" />
                  </div>
                  <div className="w-6 h-6 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 flex items-center justify-center text-[10px] text-white font-bold">
                    HQ
                  </div>
                </div>
              </div>

              {/* Mini Metrics Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                
                {/* Revenue Card */}
                <div className="bg-white border border-slate-100 rounded-2xl p-3.5 relative overflow-hidden group shadow-sm">
                  <div className="flex items-center justify-between text-slate-500 mb-1">
                    <span className="text-xs font-medium">Monthly Revenue</span>
                    <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                  </div>
                  <div className="text-lg font-bold text-slate-900">$110,000</div>
                  <div className="text-[10px] text-emerald-600 font-medium flex items-center gap-1 mt-1">
                    <span>+24.1%</span>
                    <span className="text-slate-400">vs last month</span>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-emerald-500 to-teal-400 scale-x-0 group-hover:scale-x-100 transition-transform origin-left duration-300" />
                </div>

                {/* Sales Funnel Card */}
                <div className="bg-white border border-slate-100 rounded-2xl p-3.5 relative overflow-hidden group shadow-sm">
                  <div className="flex items-center justify-between text-slate-500 mb-1">
                    <span className="text-xs font-medium">Profit margin</span>
                    <DollarSign className="w-3.5 h-3.5 text-blue-600" />
                  </div>
                  <div className="text-lg font-bold text-slate-900">32.4%</div>
                  <div className="text-[10px] text-blue-600 font-medium flex items-center gap-1 mt-1">
                    <span>+3.2%</span>
                    <span className="text-slate-400">efficiency rate</span>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-600 to-indigo-600 scale-x-0 group-hover:scale-x-100 transition-transform origin-left duration-300" />
                </div>

                {/* HR Card */}
                <div className="bg-white border border-slate-100 rounded-2xl p-3.5 relative overflow-hidden group shadow-sm">
                  <div className="flex items-center justify-between text-slate-500 mb-1">
                    <span className="text-xs font-medium">Global FTEs</span>
                    <Users className="w-3.5 h-3.5 text-cyan-500" />
                  </div>
                  <div className="text-lg font-bold text-slate-900">248</div>
                  <div className="text-[10px] text-cyan-600 font-medium flex items-center gap-1 mt-1">
                    <span>99.2%</span>
                    <span className="text-slate-400">retention score</span>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-cyan-400 to-blue-400 scale-x-0 group-hover:scale-x-100 transition-transform origin-left duration-300" />
                </div>

              </div>

              {/* Core Charts Area */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                
                {/* Revenue Growth Area Chart */}
                <div className="bg-white border border-slate-100 rounded-2xl p-3 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-600" />
                      Revenue Projection
                    </h3>
                    <span className="text-[10px] font-mono text-slate-400">6M Trend</span>
                  </div>
                  <div className="h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={miniRevenueData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#2563EB" stopOpacity={0.2}/>
                            <stop offset="95%" stopColor="#2563EB" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="name" stroke="#94a3b8" fontSize={9} tickLine={false} axisLine={false} />
                        <YAxis stroke="#94a3b8" fontSize={9} tickLine={false} axisLine={false} />
                        <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", fontSize: "10px", color: "#1e293b" }} />
                        <Area type="monotone" dataKey="revenue" stroke="#2563EB" strokeWidth={1.5} fillOpacity={1} fill="url(#colorRevenue)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Sales Conversion Funnel */}
                <div className="bg-white border border-slate-100 rounded-2xl p-3 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" />
                      Funnel Efficiency
                    </h3>
                    <span className="text-[10px] font-mono text-slate-400">Conv %</span>
                  </div>
                  <div className="h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={miniSalesData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                        <XAxis dataKey="name" stroke="#94a3b8" fontSize={8} tickLine={false} axisLine={false} />
                        <YAxis stroke="#94a3b8" fontSize={8} tickLine={false} axisLine={false} />
                        <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", fontSize: "10px", color: "#1e293b" }} />
                        <Bar dataKey="value" fill="#06B6D4" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

              </div>

              {/* Bottom Row: Recent Transaction Panel & AI Copilot Chat Module */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                
                {/* Recent Transactions List */}
                <div className="md:col-span-5 bg-white border border-slate-100 rounded-2xl p-3 space-y-2.5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-slate-800">Auditable Logs</h3>
                    <span className="text-[9px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-mono border border-blue-100">LIVE</span>
                  </div>
                  <div className="space-y-2 max-h-36 overflow-y-auto pr-1">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
                      <div className="text-left">
                        <div className="text-[10px] font-semibold text-slate-700">ACME Systems Inc.</div>
                        <div className="text-[8px] text-slate-400">Automated Purchase Order</div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] font-bold text-slate-900">$14,890</div>
                        <div className="text-[8px] text-emerald-600">Processed</div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
                      <div className="text-left">
                        <div className="text-[10px] font-semibold text-slate-700">TechCorp Sourcing</div>
                        <div className="text-[8px] text-slate-400">Sales CRM Deal Closed</div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] font-bold text-slate-900">$42,100</div>
                        <div className="text-[8px] text-emerald-600">Processed</div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="text-left">
                        <div className="text-[10px] font-semibold text-slate-700">Global Logistics Ltd</div>
                        <div className="text-[8px] text-slate-400">Consolidated Import Duty</div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] font-bold text-slate-900">$8,520</div>
                        <div className="text-[8px] text-yellow-600">Reviewing</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* AI Chat Widget (Interactive!) */}
                <div className="md:col-span-7 bg-slate-50 border border-slate-200 rounded-2xl p-3 flex flex-col justify-between shadow-sm">
                  <div className="flex items-center gap-1.5 border-b border-slate-200 pb-1.5 mb-1.5">
                    <div className="p-1 rounded-md bg-blue-50">
                      <Brain className="w-3 h-3 text-blue-600" />
                    </div>
                    <span className="text-xs font-bold text-slate-800">Interactive Copilot Assistant</span>
                  </div>

                  {/* Message Stream */}
                  <div className="space-y-2 h-[88px] overflow-y-auto pr-1 text-[10px] text-left scrollbar-thin">
                    {chatMessages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`p-1.5 rounded-lg max-w-[90%] ${
                          msg.sender === "assistant"
                            ? "bg-white text-slate-700 mr-auto border border-slate-200"
                            : "bg-blue-600 text-white ml-auto"
                        }`}
                      >
                        {msg.text}
                      </div>
                    ))}
                  </div>

                  {/* Message Input Form */}
                  <form onSubmit={handleSendMessage} className="mt-2 flex items-center gap-1.5">
                    <input
                      type="text"
                      id="hero-ai-chat-input"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Ask copilot: 'Verify revenue' or 'Check stock'..."
                      className="flex-grow bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-[10px] text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500 transition-colors"
                    />
                    <button
                      type="submit"
                      id="hero-ai-chat-send"
                      className="p-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors flex-shrink-0 cursor-pointer"
                      aria-label="Send message"
                    >
                      <Send className="w-3 h-3" />
                    </button>
                  </form>
                </div>

              </div>

            </motion.div>

            {/* Float elements */}
            <div className="absolute -bottom-6 -left-6 bg-white border border-slate-200 p-2.5 rounded-2xl shadow-xl flex items-center gap-2 pointer-events-none z-20">
              <div className="p-1 rounded-md bg-emerald-50">
                <Activity className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-left text-[10px]">
                <div className="font-semibold text-slate-850">Predictive Ledger active</div>
                <div className="text-slate-500">Anomaly engine live</div>
              </div>
            </div>

            <div className="absolute top-10 -right-8 bg-white border border-slate-200 p-2 rounded-2xl shadow-xl flex items-center gap-2 pointer-events-none z-20 hidden sm:flex">
              <Sparkles className="w-4 h-4 text-cyan-600 animate-spin-slow" />
              <div className="text-[10px] text-slate-700 font-medium">99.4% auto-matching accuracy</div>
            </div>

          </div>

        </div>
      </div>
    </section>
  );
}
