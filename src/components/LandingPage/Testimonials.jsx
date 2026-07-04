import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Star, ChevronLeft, ChevronRight, Quote, Sparkles } from "lucide-react";
import { testimonials } from "../../data/testimonials";

export default function Testimonials() {
  const [activeIndex, setActiveIndex] = useState(0);

  const handlePrev = () => {
    setActiveIndex((prev) => (prev === 0 ? testimonials.length - 1 : prev - 1));
  };

  const handleNext = () => {
    setActiveIndex((prev) => (prev === testimonials.length - 1 ? 0 : prev + 1));
  };

  return (
    <section
      id="testimonials"
      className="py-24 md:py-32 bg-transparent text-slate-900 relative overflow-hidden"
    >
      <div className="absolute top-1/2 left-1/4 w-[400px] h-[400px] bg-blue-600/5 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-16">
        
        {/* Section Header */}
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100">
            <Sparkles className="w-3.5 h-3.5" />
            Social Proof
          </span>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 font-sans">
            Endorsed by Top Operations
          </h2>
          <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto">
            Read how chief operating officers and chief financial officers are shaving days off consolidation schedules.
          </p>
        </div>

        {/* Testimonials Desktop Grid (Visible on large screens) */}
        <div className="hidden lg:grid grid-cols-2 gap-8 text-left">
          {testimonials.map((item) => (
            <motion.div
              key={item.id}
              id={`testimonial-card-desktop-${item.id}`}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="p-8 rounded-3xl bg-white/70 border border-white/50 backdrop-blur-xl relative flex flex-col justify-between hover:border-slate-200 hover:bg-white/95 shadow-[0_12px_36px_rgba(0,0,0,0.03)] hover:shadow-[0_24px_48px_-12px_rgba(0,0,0,0.06)] transition-all duration-300"
            >
              <div className="space-y-6">
                {/* 5 Stars and Quote icon */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1 text-amber-400">
                    {Array.from({ length: item.rating }).map((_, i) => (
                      <Star key={i} className="w-4 h-4 fill-current" />
                    ))}
                  </div>
                  <Quote className="w-8 h-8 text-slate-200/60" />
                </div>

                <p className="text-slate-600 text-sm md:text-base leading-relaxed italic">
                  "{item.text}"
                </p>
              </div>

              {/* Author info */}
              <div className="flex items-center gap-4 mt-8 pt-6 border-t border-slate-100">
                <img
                  src={item.avatarUrl}
                  alt={item.name}
                  referrerPolicy="no-referrer"
                  className="w-12 h-12 rounded-full object-cover border border-slate-200"
                />
                <div className="text-left">
                  <div className="text-sm font-extrabold text-slate-900">{item.name}</div>
                  <div className="text-xs text-slate-500">
                    {item.role}, <span className="text-blue-600 font-semibold">{item.company}</span>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Testimonials Mobile Carousel (Visible on smaller screens) */}
        <div className="lg:hidden relative max-w-lg mx-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeIndex}
              id={`testimonial-carousel-item-${activeIndex}`}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
              className="p-6 rounded-3xl bg-white/80 border border-white/50 backdrop-blur-xl text-left space-y-6 shadow-[0_12px_36px_rgba(0,0,0,0.03)]"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 text-amber-400">
                  {Array.from({ length: testimonials[activeIndex].rating }).map((_, i) => (
                    <Star key={i} className="w-4 h-4 fill-current" />
                  ))}
                </div>
                <Quote className="w-6 h-6 text-slate-200/60" />
              </div>

              <p className="text-slate-600 text-sm leading-relaxed italic">
                "{testimonials[activeIndex].text}"
              </p>

              <div className="flex items-center gap-4 pt-4 border-t border-slate-100">
                <img
                  src={testimonials[activeIndex].avatarUrl}
                  alt={testimonials[activeIndex].name}
                  referrerPolicy="no-referrer"
                  className="w-10 h-10 rounded-full object-cover border border-slate-200"
                />
                <div className="text-left">
                  <div className="text-sm font-bold text-slate-900">{testimonials[activeIndex].name}</div>
                  <div className="text-xs text-slate-500">
                    {testimonials[activeIndex].role}, <span className="text-blue-600">{testimonials[activeIndex].company}</span>
                  </div>
                </div>
              </div>
            </motion.div>
          </AnimatePresence>

          {/* Carousel Arrows */}
          <div className="flex items-center justify-center gap-4 mt-6">
            <button
              id="testimonial-carousel-prev"
              onClick={handlePrev}
              className="p-2.5 rounded-xl bg-white border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-50 shadow-sm transition-all cursor-pointer"
              aria-label="Previous Testimonial"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-xs font-mono text-slate-500">
              {activeIndex + 1} / {testimonials.length}
            </span>
            <button
              id="testimonial-carousel-next"
              onClick={handleNext}
              className="p-2.5 rounded-xl bg-white border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-50 shadow-sm transition-all cursor-pointer"
              aria-label="Next Testimonial"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>

      </div>
    </section>
  );
}



