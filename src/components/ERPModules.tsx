import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import * as Icons from "lucide-react";
import { erpModules, ERPModule } from "../data/modules";

export default function ERPModules() {
  const [activeModule, setActiveModule] = useState<string>("finance");

  return (
    <section
      id="modules"
      className="py-24 md:py-32 bg-transparent relative overflow-hidden"
    >
      <div className="absolute top-0 right-1/4 w-80 h-80 bg-blue-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-16">
        
        {/* Section Header */}
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-600 border border-indigo-100">
            <Icons.Boxes className="w-3.5 h-3.5" />
            Core ERP Architecture
          </span>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 font-sans">
            Fully Consolidated Modules
          </h2>
          <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto">
            Choose standard modular building blocks or integrate the entire unified suite to manage departments seamlessly.
          </p>
        </div>

        {/* Modules Layout: Sidebar selectors + Expanded Active Card Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* LEFT Sidebar list (5-Columns) */}
          <div className="lg:col-span-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2.5 max-h-[640px] overflow-y-auto pr-2 scrollbar-thin">
            {erpModules.map((module) => {
              const LucideIcon = (Icons as any)[module.iconName] || Icons.HelpCircle;
              const isSelected = activeModule === module.id;
              
              return (
                <button
                  key={module.id}
                  id={`module-select-${module.id}`}
                  onClick={() => setActiveModule(module.id)}
                  className={`flex items-center gap-3 px-4 py-3.5 rounded-2xl text-left border cursor-pointer transition-all duration-300 ${
                    isSelected
                      ? "bg-white border-slate-200/80 shadow-[0_4px_12px_rgba(0,0,0,0.04)] text-slate-900"
                      : "bg-white/40 border-slate-200/50 text-slate-500 hover:border-slate-200 hover:bg-white/80"
                  }`}
                >
                  <div className={`p-2 rounded-xl transition-all ${
                    isSelected
                      ? "bg-blue-600 text-white"
                      : "bg-slate-100 text-slate-500 group-hover:text-slate-900"
                  }`}>
                    <LucideIcon className="w-4 h-4" />
                  </div>
                  <div className="flex-grow">
                    <div className={`text-xs font-bold font-sans ${isSelected ? "text-blue-600" : "text-slate-700"}`}>
                      {module.name}
                    </div>
                    <div className="text-[10px] text-slate-400 line-clamp-1 mt-0.5">
                      {module.description}
                    </div>
                  </div>
                  <Icons.ChevronRight className={`w-4 h-4 text-slate-400 transition-transform ${isSelected ? "translate-x-1 text-blue-600" : ""}`} />
                </button>
              );
            })}
          </div>

          {/* RIGHT Expanded Display Card (7-Columns) */}
          <div className="lg:col-span-7 h-full">
            <AnimatePresence mode="wait">
              {erpModules.map((module) => {
                if (module.id !== activeModule) return null;
                const LucideIcon = (Icons as any)[module.iconName] || Icons.HelpCircle;

                return (
                  <motion.div
                    key={module.id}
                    id={`module-panel-detail-${module.id}`}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.35 }}
                    className="rounded-3xl bg-white/80 border border-white/50 p-6 md:p-8 space-y-8 shadow-[0_24px_48px_-12px_rgba(0,0,0,0.06)] backdrop-blur-xl relative overflow-hidden"
                  >
                    {/* Top corner gradient accents */}
                    <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl pointer-events-none" />

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-6">
                      <div className="flex items-center gap-3.5">
                        <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center shadow-lg">
                          <LucideIcon className="w-7 h-7" />
                        </div>
                        <div className="text-left">
                          <h3 className="text-xl font-sans font-extrabold text-slate-900">{module.name}</h3>
                          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Active ERP Module</span>
                        </div>
                      </div>
                      <div className="bg-slate-50 px-4 py-2 rounded-2xl border border-slate-200/60 text-left">
                        <div className="text-[9px] font-semibold text-slate-500 font-mono uppercase">{module.stats.label}</div>
                        <div className="text-base font-extrabold text-slate-900">{module.stats.value}</div>
                      </div>
                    </div>

                    <div className="space-y-4 text-left">
                      <h4 className="text-xs font-mono font-bold text-blue-600 uppercase tracking-widest">MODULE ARCHITECTURE SUMMARY</h4>
                      <p className="text-slate-600 text-sm md:text-base leading-relaxed">
                        {module.description}
                      </p>
                    </div>

                    {/* Highlights Bullet List */}
                    <div className="space-y-3.5 text-left pt-2">
                      <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-widest">KEY INTEGRATED HIGHLIGHTS</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {module.highlights.map((hl, idx) => (
                          <div key={idx} className="bg-slate-50 border border-slate-200/60 p-3 rounded-xl flex items-start gap-2.5">
                            <Icons.CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                            <span className="text-xs font-medium text-slate-700">{hl}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Realistic Miniature Dashboard Box inside module panel */}
                    <div className="bg-slate-950 rounded-2xl p-4 border border-slate-900 relative text-left">
                      <div className="flex items-center justify-between mb-3 border-b border-slate-900 pb-2">
                        <span className="text-[10px] font-mono text-slate-500">MODULE PREVIEW LEDGER</span>
                        <div className="flex items-center gap-1.5 text-[9px] text-emerald-400 font-mono">
                          <Icons.Activity className="w-3.5 h-3.5 animate-pulse" />
                          TELEMETRY CONNECTED
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-[9px] text-slate-500 font-semibold uppercase">API Gateway State</div>
                          <div className="text-xs font-bold text-white mt-0.5 flex items-center gap-1">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            Active & Ready
                          </div>
                        </div>
                        <div>
                          <div className="text-[9px] text-slate-500 font-semibold uppercase">Data Locality</div>
                          <div className="text-xs font-bold text-white mt-0.5">Secure Multi-Region</div>
                        </div>
                      </div>
                    </div>

                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>

        </div>

      </div>
    </section>
  );
}
