import { motion } from "motion/react";

export default function TrustedCompanies() {
  const companies = [
    { name: "Microsoft", logoColor: "hover:text-blue-500" },
    { name: "Google Cloud", logoColor: "hover:text-red-400" },
    { name: "AWS", logoColor: "hover:text-amber-500" },
    { name: "Oracle", logoColor: "hover:text-red-500" },
    { name: "SAP", logoColor: "hover:text-blue-600" },
    { name: "IBM", logoColor: "hover:text-blue-400" },
    { name: "Intel", logoColor: "hover:text-cyan-400" },
    { name: "Cisco", logoColor: "hover:text-sky-500" }
  ];

  return (
    <section
      id="trusted-companies"
      className="py-12 border-y border-slate-200/60 bg-white/40 backdrop-blur-md"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-slate-500 mb-8">
          TRUSTED BY MODERN BUSINESSES AND FORTUNE 500S
        </h2>
        
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-8 items-center justify-items-center opacity-70">
          {companies.map((company, index) => (
            <motion.div
              key={company.name}
              id={`company-logo-${index}`}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: index * 0.05 }}
              whileHover={{ scale: 1.05 }}
              className={`flex items-center gap-1.5 font-bold tracking-tight text-slate-400 select-none cursor-pointer transition-colors duration-300 ${company.logoColor}`}
            >
              <div className="w-2.5 h-2.5 rounded-full bg-current opacity-80" />
              <span className="font-sans text-base tracking-tight">{company.name}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
