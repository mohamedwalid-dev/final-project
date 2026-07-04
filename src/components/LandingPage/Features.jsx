import { motion } from "framer-motion";
import * as Icons from "lucide-react";
import { features } from "../../data/features";

export default function Features() {
  return (
    <section
      id="features"
      className="py-24 md:py-32 bg-transparent relative overflow-hidden"
    >
      {/* Background radial glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-50/5 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center space-y-16">
        
        {/* Section Header */}
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100"
          >
            <Icons.Sparkles className="w-3.5 h-3.5" />
            Capabilities Matrix
          </motion.div>
          
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 font-sans"
          >
            Everything You Need to Run Your Business
          </motion.h2>
          
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto"
          >
            Ditch disconnected SaaS subscriptions. Our unified ledger merges operational telemetry to automate entire departments automatically.
          </motion.p>
        </div>

        {/* Features 12-Column Responsive Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 text-left">
          {features.map((feature, index) => {
            // Dynamically lookup the icon component
            const LucideIcon = Icons[feature.iconName] || Icons.HelpCircle;

            return (
              <motion.div
                key={feature.id}
                id={`feature-card-${feature.id}`}
                initial={{ opacity: 0, y: 25 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.5, delay: (index % 4) * 0.1 }}
                whileHover={{ y: -8 }}
                className="relative group rounded-3xl bg-white/70 border border-white/50 p-6 md:p-8 backdrop-blur-xl hover:border-slate-200 hover:bg-white/95 hover:shadow-[0_24px_48px_-12px_rgba(0,0,0,0.06)] transition-all duration-300"
              >
                {/* Accent glow on hover */}
                <div className="absolute inset-0 rounded-3xl bg-gradient-to-tr from-blue-500/0 via-indigo-500/0 to-cyan-500/0 group-hover:from-blue-500/2 group-hover:to-cyan-500/2 transition-all duration-500 pointer-events-none" />

                {/* Card Icon Header */}
                <div className="mb-6 flex items-center justify-between">
                  <div className={`w-12 h-12 rounded-2xl bg-gradient-to-tr ${feature.gradient} p-2.5 flex items-center justify-center text-white shadow-lg`}>
                    <LucideIcon className="w-full h-full" />
                  </div>
                  {feature.badge && (
                    <span className="text-[10px] uppercase tracking-widest bg-blue-50 border border-blue-100 text-blue-600 px-2 py-0.5 rounded-full font-semibold">
                      {feature.badge}
                    </span>
                  )}
                </div>

                {/* Card Text */}
                <h3 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-blue-600 transition-colors">
                  {feature.title}
                </h3>
                <p className="text-sm text-slate-500 leading-relaxed">
                  {feature.description}
                </p>

                {/* Floating link indicator */}
                <div className="mt-6 flex items-center gap-1.5 text-xs text-blue-600 font-semibold group-hover:text-blue-700 select-none cursor-pointer">
                  <span>Learn module details</span>
                  <Icons.ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}



