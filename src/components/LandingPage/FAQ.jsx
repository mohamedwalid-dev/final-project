import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Minus, HelpCircle } from "lucide-react";
import { faqs } from "../../data/faq";

export default function FAQ() {
  const [expandedId, setExpandedId] = useState(null);

  const handleToggle = (id) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <section
      id="faq"
      className="py-24 md:py-32 bg-transparent text-slate-900 relative overflow-hidden"
    >
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-50/10 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-16">
        
        {/* Section Header */}
        <div className="text-center space-y-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-cyan-50 text-cyan-700 border border-cyan-100">
            <HelpCircle className="w-3.5 h-3.5" />
            Common Inquiries
          </span>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 font-sans">
            Frequently Asked Questions
          </h2>
          <p className="text-slate-600 text-base sm:text-lg max-w-xl mx-auto">
            Find immediate answers regarding data security, transition pathways, and modules.
          </p>
        </div>

        {/* Accordion List */}
        <div className="space-y-4">
          {faqs.map((faq) => {
            const isExpanded = expandedId === faq.id;

            return (
              <div
                key={faq.id}
                id={`faq-item-box-${faq.id}`}
                className="rounded-2xl border border-white/50 bg-white/70 overflow-hidden backdrop-blur-xl hover:border-slate-200 shadow-[0_8px_30px_rgba(0,0,0,0.02)] hover:shadow-[0_16px_40px_rgba(0,0,0,0.04)] transition-all"
              >
                <button
                  id={`faq-trigger-${faq.id}`}
                  onClick={() => handleToggle(faq.id)}
                  className="w-full px-6 py-5 flex items-center justify-between text-left text-base font-bold text-slate-900 hover:text-blue-600 cursor-pointer transition-colors"
                >
                  <span>{faq.question}</span>
                  <div className={`p-1.5 rounded-lg bg-slate-50 text-slate-500 transition-transform ${isExpanded ? "rotate-180 text-blue-600 bg-blue-50" : ""}`}>
                    {isExpanded ? <Minus className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                  </div>
                </button>

                <AnimatePresence initial={false}>
                  {isExpanded && (
                    <motion.div
                      id={`faq-content-pane-${faq.id}`}
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25, ease: "easeInOut" }}
                    >
                      <div className="px-6 pb-6 text-slate-600 text-xs sm:text-sm leading-relaxed border-t border-slate-100 pt-4 text-left">
                        {faq.answer}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
}



