import { motion } from "motion/react";
import * as Icons from "lucide-react";

export default function Benefits() {
  const whyChooseUsItems = [
    {
      id: "ai-decisions",
      title: "AI-Powered Decisions",
      description: "Harness proactive predictive forecasting, not retrospective logging. Shift from counting past ledger entries to forecasting tomorrow's demand structures.",
      iconName: "BrainCircuit",
      color: "text-blue-400"
    },
    {
      id: "cloud-native",
      title: "Cloud Native Access",
      description: "Deploy globally, coordinate instantly. Access unified ledgers securely on any tablet, mobile, or workstation on robust serverless backbones.",
      iconName: "Cloud",
      color: "text-indigo-400"
    },
    {
      id: "enterprise-security",
      title: "Enterprise Security Core",
      description: "Guarded by industry-standard TLS 1.3, AES-256 rest encryption, multi-factor SAML single sign-on, SOC 2 compliance registries, and RBAC policies.",
      iconName: "ShieldAlert",
      color: "text-emerald-400"
    },
    {
      id: "fast-performance",
      title: "Hypersonic Performance",
      description: "Database transaction queries resolve in under 1.2s. Dynamic spreadsheet charts render at a highly performant 60 frames per second.",
      iconName: "Zap",
      color: "text-amber-400"
    },
    {
      id: "scalable-arch",
      title: "Scalable Architecture",
      description: "Easily accommodate team expansions from 15 core staff to 15,000 global administrators with serverless horizontal auto-scaling nodes.",
      iconName: "Network",
      color: "text-cyan-400"
    },
    {
      id: "easy-integrations",
      title: "Seamless Third-Party APIs",
      description: "Native developer-friendly webhooks and RESTful endpoints integrate with Slack, Stripe, Jira, HubSpot, Shopify, and Microsoft 365.",
      iconName: "Puzzle",
      color: "text-fuchsia-400"
    },
    {
      id: "24-7-support",
      title: "24/7 Professional Support",
      description: "Our dedicated regional technical engineers back you with strict 1-hour priority SLAs, handling custom ledger mapping assistance.",
      iconName: "Headphones",
      color: "text-rose-400"
    },
    {
      id: "modern-ux",
      title: "Modern Executive UX",
      description: "A highly responsive design styled with generous negative space, sleek typography pairings, intuitive menus, and dark-mode comfort.",
      iconName: "Layout",
      color: "text-teal-400"
    }
  ];

  return (
    <section
      id="why-us"
      className="py-24 md:py-32 bg-transparent border-y border-slate-200/60 relative overflow-hidden"
    >
      <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-16">
        
        {/* Section Header */}
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100">
            <Icons.Layers className="w-3.5 h-3.5" />
            Competitive Edge
          </span>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 font-sans">
            Why Modern CFOs Choose Prime
          </h2>
          <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto">
            Traditional systems keep you stuck in the past. We combine modern interface design with predictive analytics.
          </p>
        </div>

        {/* Timeline Layout Grid (2 Columns, left/right alternate) */}
        <div className="relative max-w-4xl mx-auto">
          {/* Vertical central timeline line */}
          <div className="absolute left-4 md:left-1/2 top-2 bottom-2 w-0.5 bg-gradient-to-b from-blue-500 via-indigo-500 to-cyan-500 opacity-20" />

          <div className="space-y-12">
            {whyChooseUsItems.map((item, index) => {
              const LucideIcon = (Icons as any)[item.iconName] || Icons.HelpCircle;
              const isEven = index % 2 === 0;

              return (
                <div
                  key={item.id}
                  id={`benefit-timeline-${item.id}`}
                  className={`flex flex-col md:flex-row items-start md:items-center relative ${
                    isEven ? "md:flex-row-reverse" : ""
                  }`}
                >
                  {/* Timeline point indicator */}
                  <div className="absolute left-4 md:left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-white border-2 border-slate-200 flex items-center justify-center z-20 text-slate-400 group-hover:border-blue-500">
                    <div className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />
                  </div>

                  {/* Spacer Column for desktop */}
                  <div className="hidden md:block w-1/2 px-8" />

                  {/* Content Column (1/2 width) */}
                  <motion.div
                    initial={{ opacity: 0, x: isEven ? 30 : -30 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.5, delay: 0.05 }}
                    className="w-full md:w-1/2 pl-12 md:pl-0 md:px-8 text-left"
                  >
                    <div className="p-6 rounded-2xl bg-white/70 border border-white/50 backdrop-blur-xl hover:border-slate-200 hover:bg-white/95 shadow-[0_8px_30px_rgba(0,0,0,0.02)] hover:shadow-[0_16px_40px_rgba(0,0,0,0.05)] transition-all duration-300">
                      <div className="flex items-center gap-3 mb-3">
                        <div className={`p-2 rounded-lg bg-slate-50 ${item.color.replace('400', '600')}`}>
                          <LucideIcon className="w-5 h-5" />
                        </div>
                        <h3 className="text-base font-bold text-slate-900 font-sans">{item.title}</h3>
                      </div>
                      <p className="text-slate-500 text-xs sm:text-sm leading-relaxed">
                        {item.description}
                      </p>
                    </div>
                  </motion.div>
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </section>
  );
}
