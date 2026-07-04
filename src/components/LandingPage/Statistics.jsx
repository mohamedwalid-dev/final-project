import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Award, ShieldAlert, Zap, Cpu, Users } from "lucide-react";

export default function Statistics() {
  const [companiesCount, setCompaniesCount] = useState(0);
  const [usersCount, setUsersCount] = useState(0);
  const [productivity, setProductivity] = useState(0);
  const [decisions, setDecisions] = useState(0);

  useEffect(() => {
    let active = true;
    
    // Count up simulator
    const duration = 2000; // ms
    const intervalTime = 40; // ms
    const steps = duration / intervalTime;

    let step = 0;
    const timer = setInterval(() => {
      if (!active) return;
      step++;
      
      setCompaniesCount(Math.min(500, Math.round((500 / steps) * step)));
      setUsersCount(Math.min(100, Math.round((100 / steps) * step)));
      setProductivity(Math.min(40, Math.round((40 / steps) * step)));
      setDecisions(Math.min(3, Math.round((3 / steps) * step)));

      if (step >= steps) {
        clearInterval(timer);
      }
    }, intervalTime);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const stats = [
    {
      id: "companies",
      value: `${companiesCount}+`,
      label: "Enterprise Partners",
      desc: "Fortune 500s trusting our automated platform.",
      icon: Award,
      color: "text-blue-400"
    },
    {
      id: "users",
      value: `${usersCount}K+`,
      label: "Active Daily Operators",
      desc: "Administrators coordinating business ledgers.",
      icon: Users,
      color: "text-indigo-400"
    },
    {
      id: "uptime",
      value: "99.99%",
      label: "Server Cluster Uptime",
      desc: "Backed by redundant localized region clouds.",
      icon: ShieldAlert,
      color: "text-cyan-400"
    },
    {
      id: "productivity",
      value: `${productivity}%`,
      label: "FTE Productivity Lift",
      desc: "Measured after automated invoice mapping.",
      icon: Zap,
      color: "text-amber-400"
    },
    {
      id: "decisions",
      value: `${decisions}X`,
      label: "Faster Board Decisions",
      desc: "Leveraging natural language dashboard querying.",
      icon: Cpu,
      color: "text-emerald-400"
    }
  ];

  return (
    <section
      id="statistics"
      className="py-16 md:py-24 bg-white/40 backdrop-blur-md border-y border-slate-200/60 text-slate-800 relative overflow-hidden"
    >
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[300px] bg-blue-50/10 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 text-center">
          {stats.map((stat, idx) => {
            const StatIcon = stat.icon;
            return (
              <motion.div
                key={stat.id}
                id={`stat-counter-box-${stat.id}`}
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                className="space-y-2 text-center flex flex-col items-center"
              >
                <div className={`p-2.5 rounded-xl bg-white border border-slate-200 shadow-sm ${stat.color.replace('400', '600')} mb-1 flex items-center justify-center`}>
                  <StatIcon className="w-5 h-5" />
                </div>
                <div className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 font-sans">
                  {stat.value}
                </div>
                <div className="text-xs sm:text-sm font-bold text-slate-700 font-sans">
                  {stat.label}
                </div>
                <p className="text-[10px] text-slate-500 max-w-[140px] mx-auto leading-relaxed">
                  {stat.desc}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}



