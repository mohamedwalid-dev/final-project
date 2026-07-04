import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Brain,
  Sparkles,
  ArrowRight,
  TrendingUp,
  LineChart,
  Terminal,
  Activity,
  CheckCircle2,
  Lock,
  Zap,
  Play,
  RotateCcw
} from "lucide-react";

export default function AISection() {
  const [activeTask, setActiveTask] = useState<string>("forecast");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [taskResult, setTaskResult] = useState<any>({
    title: "Projected Q3 & Q4 Revenue Growth",
    metrics: [
      { label: "Optimistic Forecast", value: "$1.48M", change: "+18%" },
      { label: "Baseline Target", value: "$1.25M", change: "On Target" },
      { label: "Pessimistic Floor", value: "$1.02M", change: "-8%" }
    ],
    confidence: "94.8% AI Confidence Score",
    statusText: "Analysis finalized based on last 24 months ledger performance."
  });

  const handleRunTask = (taskType: string) => {
    setIsProcessing(true);
    setActiveTask(taskType);
    
    setTimeout(() => {
      setIsProcessing(false);
      if (taskType === "forecast") {
        setTaskResult({
          title: "Projected Q3 & Q4 Revenue Growth",
          metrics: [
            { label: "Optimistic Forecast", value: "$1.48M", change: "+18%" },
            { label: "Baseline Target", value: "$1.25M", change: "On Target" },
            { label: "Pessimistic Floor", value: "$1.02M", change: "-8%" }
          ],
          confidence: "94.8% AI Confidence Score",
          statusText: "Analysis finalized based on last 24 months ledger performance."
        });
      } else if (taskType === "anomalies") {
        setTaskResult({
          title: "Automated Ledger Audit Results",
          metrics: [
            { label: "Anomalies Checked", value: "14,802", change: "100%" },
            { label: "Flagged Risks", value: "1 Pending", change: "High Priority" },
            { label: "Resolution State", value: "Auto-Drafted", change: "Queue" }
          ],
          confidence: "99.2% Audit Accuracies",
          statusText: "Duplicate draft billing #INV-2026-94 was flagged and queued."
        });
      } else if (taskType === "automation") {
        setTaskResult({
          title: "Dynamic Supply Chain Automation",
          metrics: [
            { label: "Trigger Threshold", value: "<15 Units", change: "Active" },
            { label: "Vendor Contacts", value: "4 Engaged", change: "RFQ" },
            { label: "Avg Cost Savings", value: "14.2%", change: "Negotiated" }
          ],
          confidence: "97.5% Autopilot Efficiency",
          statusText: "Reordered model X-8 components. Sent requests to top 3 rated providers."
        });
      }
    }, 850);
  };

  const tasks = [
    { id: "forecast", label: "Predict Revenue Runway", icon: TrendingUp },
    { id: "anomalies", label: "Detect Bookkeeping Anomalies", icon: Activity },
    { id: "automation", label: "Trigger Supply Procurement", icon: Zap }
  ];

  return (
    <section
      id="ai-assistant"
      className="py-24 md:py-32 bg-transparent relative overflow-hidden border-y border-slate-200/60"
    >
      {/* Decorative Blur Circle */}
      <div className="absolute top-1/3 -right-20 w-[450px] h-[440px] bg-cyan-100/30 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -left-20 w-[400px] h-[400px] bg-blue-100/30 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-16 items-center">
          
          {/* LEFT COLUMN: Large AI Interactive Interactive Illustration */}
          <div className="lg:col-span-6 relative">
            <div className="relative rounded-3xl bg-white/70 border border-white/50 p-6 md:p-8 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.08)] backdrop-blur-xl overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500" />
              
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
                  <span className="text-xs font-mono text-slate-500">AI AGENT: ACTIVE TELEMETRY</span>
                </div>
                <div className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-mono border border-blue-100 flex items-center gap-1">
                  <Brain className="w-3 h-3 text-cyan-600" />
                  COPILOT RUNNING
                </div>
              </div>

              {/* Quick Task Triggers */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-6">
                {tasks.map((task) => {
                  const TaskIcon = task.icon;
                  return (
                    <button
                      key={task.id}
                      id={`ai-task-btn-${task.id}`}
                      onClick={() => handleRunTask(task.id)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-xl text-[11px] font-semibold text-left transition-all border cursor-pointer ${
                        activeTask === task.id
                          ? "bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-500/20"
                          : "bg-white border-slate-200 text-slate-600 hover:border-slate-350 hover:bg-slate-50 hover:text-slate-900 shadow-sm"
                      }`}
                    >
                      <TaskIcon className="w-4 h-4 flex-shrink-0" />
                      <span>{task.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Dynamic Console Preview Box */}
              <div className="bg-slate-950 rounded-2xl p-5 border border-slate-900 h-56 flex flex-col justify-between relative">
                <AnimatePresence mode="wait">
                  {isProcessing ? (
                    <motion.div
                      key="loading"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm rounded-2xl"
                    >
                      <Brain className="w-10 h-10 text-cyan-400 animate-bounce mb-3" />
                      <div className="text-xs text-slate-300 font-mono flex items-center gap-2">
                        <Terminal className="w-3.5 h-3.5 text-blue-400" />
                        Analyzing ledger matrices...
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="result"
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="space-y-4 flex flex-col h-full justify-between"
                    >
                      <div>
                        <div className="text-[10px] text-blue-400 font-mono font-bold uppercase tracking-wider mb-1">
                          COGNITIVE INSIGHT GENERATOR
                        </div>
                        <h4 className="text-sm font-bold text-white font-sans">{taskResult.title}</h4>
                      </div>

                      {/* Display Metrics Grid */}
                      <div className="grid grid-cols-3 gap-3">
                        {taskResult.metrics.map((m: any, i: number) => (
                          <div key={i} className="bg-slate-900 p-2.5 rounded-lg border border-slate-800 text-left">
                            <div className="text-[9px] text-slate-400 truncate font-semibold">{m.label}</div>
                            <div className="text-sm font-extrabold text-white mt-0.5">{m.value}</div>
                            <div className="text-[8px] text-emerald-400 font-medium mt-0.5">{m.change}</div>
                          </div>
                        ))}
                      </div>

                      <div className="flex items-center justify-between text-[10px] text-slate-400 border-t border-slate-900 pt-2 font-mono">
                        <span className="flex items-center gap-1 text-emerald-400 font-semibold">
                          <CheckCircle2 className="w-3 h-3" />
                          {taskResult.confidence}
                        </span>
                        <span>{taskResult.statusText}</span>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Bottom interactive hint */}
              <div className="mt-4 text-center text-xs text-slate-500 font-mono">
                Click any option above to see how our AI engine acts instantly.
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: Copywriting & Bulletpoints */}
          <div className="lg:col-span-6 text-left space-y-8">
            <div className="space-y-4">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-cyan-50 text-cyan-700 border border-cyan-100">
                <Sparkles className="w-3.5 h-3.5" />
                Next Generation Automation
              </span>
              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 font-sans">
                Meet Your AI Business Assistant
              </h2>
              <p className="text-slate-600 text-base sm:text-lg leading-relaxed">
                Our intelligent assistant automates repetitive bookkeeping workflows, monitors critical operations, projects financial runway tables, and resolves tier-1 tickets automatically.
              </p>
            </div>

            {/* Bullet points (Aesthetic items with beautiful layouts) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { title: "Predict future revenue", desc: "Forecast seasonal cash flows accurately." },
                { title: "Detect financial anomalies", desc: "Flag double billing and entry errors." },
                { title: "Generate boardroom reports", desc: "Instant charts in natural language." },
                { title: "Natural language search", desc: "Query databases like chatting with friends." },
                { title: "Workflow automation", desc: "Auto-reconcile invoices across departments." },
                { title: "Smart recommendations", desc: "Avoid stockouts with reorder notifications." }
              ].map((bullet, index) => (
                <div key={index} className="flex gap-3">
                  <div className="w-5 h-5 rounded-full bg-blue-50 flex items-center justify-center text-blue-600 flex-shrink-0 mt-0.5 border border-blue-100">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">{bullet.title}</h4>
                    <p className="text-xs text-slate-500">{bullet.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-2">
              <button
                id="ai-section-demo-btn"
                onClick={() => handleRunTask("anomalies")}
                className="relative px-6 py-3.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 shadow-md shadow-blue-500/10 hover:shadow-lg hover:shadow-blue-500/20 transition-all cursor-pointer flex items-center gap-2"
              >
                <span>Trigger Intelligent Audit</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>

          </div>

        </div>
      </div>
    </section>
  );
}
