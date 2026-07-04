import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { ArrowRight, Sparkles, PhoneCall, CheckCircle2, X } from "lucide-react";

export default function CallToAction() {
  const navigate = useNavigate();
  const [notification, setNotification] = useState<string | null>(null);

  return (
    <section
      id="contact"
      className="py-24 bg-transparent text-slate-900 relative overflow-hidden"
    >
      {/* Confetti / Success toast */}
      <AnimatePresence>
        {notification && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-6 right-6 z-50 max-w-sm p-4 bg-white/95 backdrop-blur-xl border border-emerald-200 rounded-2xl shadow-xl flex items-start gap-3"
          >
            <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div className="flex-1 text-left">
              <h5 className="text-xs font-bold text-slate-900">Demo Scheduled</h5>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{notification}</p>
            </div>
            <button
              onClick={() => setNotification(null)}
              className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-50 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        
        {/* Giant Glassmorphic Outer Box */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="relative rounded-[40px] bg-white/70 border border-white/50 backdrop-blur-2xl p-8 sm:p-12 lg:p-20 overflow-hidden text-center shadow-[0_20px_50px_rgba(0,0,0,0.03)]"
        >
          {/* Decorative absolute blur elements */}
          <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-cyan-100/30 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-blue-100/30 rounded-full blur-3xl pointer-events-none" />
          
          <div className="relative z-10 max-w-3xl mx-auto space-y-8">
            
            {/* Small Badge icon */}
            <div className="flex justify-center">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-100">
                <Sparkles className="w-3.5 h-3.5" />
                Next Generation Ledger
              </span>
            </div>

            {/* Headline */}
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-900 font-sans leading-tight">
              Ready to Transform Your Business?
            </h2>

            {/* Description */}
            <p className="text-slate-600 text-sm sm:text-base md:text-lg leading-relaxed max-w-xl mx-auto">
              Start using Prime today and streamline every single aspect of your organization on a unified ledger.
            </p>

            {/* Action Buttons */}
            <div className="flex justify-center pt-4">
              <button
                id="cta-btn-login"
                onClick={() => navigate("/login")}
                className="px-8 py-4 bg-blue-600 text-white hover:bg-blue-700 font-bold text-sm sm:text-base rounded-2xl shadow-[0_4px_20px_rgba(37,99,235,0.25)] hover:shadow-[0_4px_24px_rgba(37,99,235,0.35)] active:scale-98 transition-all cursor-pointer flex items-center justify-center gap-2 group w-full sm:w-auto"
              >
                <span>Login Now</span>
                <ArrowRight className="w-5 h-5 text-white group-hover:translate-x-1 transition-transform" />
              </button>
            </div>

            {/* Micro details */}
            <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-slate-500 pt-4 font-sans">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>No Subscription Required</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Completely Free Prime Platform</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Access Your Dashboard Instantly</span>
              </div>
            </div>

          </div>
        </motion.div>
      </div>
    </section>
  );
}
