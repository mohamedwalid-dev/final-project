import { Hexagon, Sparkles, MessageSquare, Globe, Mail, PhoneCall } from "lucide-react";

const TwitterIcon = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z" />
  </svg>
);

const GithubIcon = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
    <path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
);

const LinkedinIcon = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
    <rect width="4" height="12" x="2" y="9" />
    <circle cx="4" cy="4" r="2" />
  </svg>
);



export default function Footer({ onNavigate }) {
  const currentYear = new Date().getFullYear();

  const companyLinks = [
    { label: "About Us", id: "home" },
    { label: "Platform Features", id: "features" },
    { label: "ERP Modules", id: "modules" },
    { label: "System Analytics", id: "analytics" }
  ];

  const resourceLinks = [
    { label: "Developer REST API Docs", href: "#" },
    { label: "System Integration Guide", href: "#" },
    { label: "Knowledge base", href: "#" },
    { label: "Client support SLA", href: "#" },
    { label: "Status dashboard", href: "#" }
  ];

  const legalLinks = [
    { label: "Security Registry", href: "#" },
    { label: "Privacy Policy", href: "#" },
    { label: "Terms of Service", href: "#" },
    { label: "GDPR Compliance", href: "#" },
    { label: "Corporate Governance", href: "#" }
  ];

  const handleLinkClick = (e, sectionId) => {
    e.preventDefault();
    onNavigate(sectionId);
  };

  return (
    <footer
      id="footer"
      className="bg-white/40 backdrop-blur-md text-slate-600 text-xs sm:text-sm border-t border-slate-200/60 pt-16 pb-12 relative overflow-hidden"
    >
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-blue-600/5 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        
        {/* Top footer columns */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-8 pb-12 border-b border-slate-200/60">
          
          {/* Logo & Pitch column (4-Columns) */}
          <div className="lg:col-span-4 space-y-6 text-left">
            <div className="flex items-center gap-2 cursor-pointer group" onClick={(e) => handleLinkClick(e, "home")}>
              <div className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-600 p-0.5">
                <Hexagon className="w-4 h-4 text-white fill-white/10" />
              </div>
              <span className="font-sans font-bold text-lg tracking-tight text-slate-900 flex items-center gap-1">
                Prime
              </span>
            </div>
            
            <p className="text-slate-500 leading-relaxed max-w-sm">
              Next generation, serverless AI-powered Enterprise Resource Planning system consolidating corporate ledgers, human resource sheets, and supply chain telemetry through Prime.
            </p>

            <div className="space-y-2 text-slate-500 font-mono text-[11px]">
              <div className="flex items-center gap-2">
                <Globe className="w-3.5 h-3.5 text-blue-600" />
                <span>Multi-region Cloud Active</span>
              </div>
              <div className="flex items-center gap-2">
                <Mail className="w-3.5 h-3.5 text-indigo-600" />
                <span>desk@prime.enterprise</span>
              </div>
              <div className="flex items-center gap-2">
                <PhoneCall className="w-3.5 h-3.5 text-cyan-600" />
                <span>+1 (800) 555-PRIME</span>
              </div>
            </div>
          </div>

          {/* Links columns (8-Columns total) */}
          <div className="lg:col-span-8 grid grid-cols-2 sm:grid-cols-3 gap-8">
            
            {/* Company links */}
            <div className="text-left space-y-4">
              <h4 className="text-slate-900 font-sans font-bold text-xs uppercase tracking-wider">Company</h4>
              <ul className="space-y-2.5">
                {companyLinks.map((link) => (
                  <li key={link.label}>
                    <a
                      href={`#${link.id}`}
                      onClick={(e) => handleLinkClick(e, link.id)}
                      className="hover:text-slate-900 transition-colors"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            {/* Resources links */}
            <div className="text-left space-y-4">
              <h4 className="text-slate-900 font-sans font-bold text-xs uppercase tracking-wider">Resources</h4>
              <ul className="space-y-2.5">
                {resourceLinks.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      onClick={(e) => { e.preventDefault(); console.log(`Documentation mapping loaded for: ${link.label}`); }}
                      className="hover:text-slate-900 transition-colors"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            {/* Legal / Compliance links */}
            <div className="text-left space-y-4">
              <h4 className="text-slate-900 font-sans font-bold text-xs uppercase tracking-wider">Compliance</h4>
              <ul className="space-y-2.5">
                {legalLinks.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      onClick={(e) => { e.preventDefault(); console.log(`Compliance log secured for: ${link.label}`); }}
                      className="hover:text-slate-900 transition-colors"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

          </div>

        </div>

        {/* Bottom row: copyright and socials */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-slate-500 text-xs text-center">
          <div>
            © {currentYear} Prime, Inc. All rights reserved. SOC2 Certified.
          </div>

          {/* Socials */}
          <div className="flex items-center gap-4">
            <a href="#" onClick={(e) => e.preventDefault()} className="hover:text-slate-900 hover:bg-slate-50 p-2 rounded-lg bg-white border border-slate-200 shadow-sm transition-colors" aria-label="Twitter social link">
              <TwitterIcon className="w-4 h-4" />
            </a>
            <a href="#" onClick={(e) => e.preventDefault()} className="hover:text-slate-900 hover:bg-slate-50 p-2 rounded-lg bg-white border border-slate-200 shadow-sm transition-colors" aria-label="Github repository link">
              <GithubIcon className="w-4 h-4" />
            </a>
            <a href="#" onClick={(e) => e.preventDefault()} className="hover:text-slate-900 hover:bg-slate-50 p-2 rounded-lg bg-white border border-slate-200 shadow-sm transition-colors" aria-label="LinkedIn profile link">
              <LinkedinIcon className="w-4 h-4" />
            </a>
            <a href="#" onClick={(e) => e.preventDefault()} className="hover:text-slate-900 hover:bg-slate-50 p-2 rounded-lg bg-white border border-slate-200 shadow-sm transition-colors" aria-label="Community message board link">
              <MessageSquare className="w-4 h-4" />
            </a>
          </div>
        </div>

      </div>
    </footer>
  );
}



