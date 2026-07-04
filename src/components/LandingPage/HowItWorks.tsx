import { motion } from "motion/react";
import { Link, Settings, Sliders, Play, Cpu, ArrowRight } from "lucide-react";

export default function HowItWorks() {
  const steps = [
    {
      step: "01",
      title: "Securely Connect Your Business Platforms",
      description: "Connect your bank accounts, database caches, sales logs, and employee registers with one click. Our SOC-2 cloud automatically maps database schemas securely.",
      icon: Link,
      gradient: "from-blue-500 to-indigo-500"
    },
    {
      step: "02",
      title: "Select & Tailor Your ERP Modules",
      description: "Choose and customize only the building blocks you require, from automated invoice reconciliation and multi-state payrolls to advanced warehouse barcode pathways.",
      icon: Sliders,
      gradient: "from-indigo-500 to-cyan-500"
    },
    {
      step: "03",
      title: "Let AI Automate Your Operational Workflows",
      description: "Sit back and watch the AI reconcile matching bank records, draft responses for incoming client tickets, and coordinate safe reorders before warehouses empty.",
      icon: Cpu,
      gradient: "from-cyan-500 to-blue-500"
    }
  ];

  return (
    <section
      id="how-it-works"
      className="py-24 md:py-32 bg-transparent relative overflow-hidden"
    >
      <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-blue-600/5 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center space-y-16">
        
        {/* Section Header */}
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-cyan-50 text-cyan-700 border border-cyan-100">
            <Play className="w-3.5 h-3.5" />
            Simple Operations
          </span>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 font-sans">
            How Prime Streamlines Your Enterprise
          </h2>
          <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto">
            Get up and running with a unified operational ledger in three simple configuration steps.
          </p>
        </div>

        {/* Steps Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-left relative">
          
          {/* Arrow vectors connecting cards for desktop */}
          <div className="hidden md:block absolute top-1/2 left-[28%] right-[28%] -translate-y-1/2 h-0.5 border-t border-dashed border-slate-200 z-0 pointer-events-none" />

          {steps.map((item, index) => {
            const StepIcon = item.icon;
            return (
              <motion.div
                key={item.step}
                id={`step-card-${item.step}`}
                initial={{ opacity: 0, y: 25 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.15 }}
                className="relative bg-white/70 border border-white/50 p-8 rounded-3xl backdrop-blur-xl hover:border-slate-200 hover:bg-white/95 shadow-[0_12px_36px_rgba(0,0,0,0.03)] hover:shadow-[0_24px_48px_-12px_rgba(0,0,0,0.06)] transition-all group z-10"
              >
                {/* Step Number Badge */}
                <div className={`absolute -top-4 left-8 text-xs font-mono font-bold px-3 py-1 rounded-full bg-gradient-to-r ${item.gradient} text-white shadow-md`}>
                  STEP {item.step}
                </div>

                {/* Step Icon */}
                <div className="w-12 h-12 rounded-2xl bg-slate-50 border border-slate-200/60 flex items-center justify-center text-blue-600 mb-6 group-hover:scale-105 transition-transform">
                  <StepIcon className="w-5 h-5 text-cyan-600" />
                </div>

                {/* Text description */}
                <h3 className="text-lg font-bold text-slate-900 mb-3 group-hover:text-blue-600 transition-colors">
                  {item.title}
                </h3>
                <p className="text-slate-500 text-sm leading-relaxed">
                  {item.description}
                </p>

                {index < 2 && (
                  <div className="md:hidden mt-6 flex justify-center text-slate-400">
                    <ArrowRight className="w-5 h-5 rotate-90" />
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
