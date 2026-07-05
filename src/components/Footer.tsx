import React from "react";
import { Hexagon, Sparkles, MessageSquare, Globe, Mail, PhoneCall } from "lucide-react";

// lucide-react no longer ships brand/logo icons (Twitter, Github, Linkedin, etc.)
// so we define lightweight inline SVG replacements with the same usage pattern.
const TwitterIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path d="M23.643 4.937c-.835.37-1.732.62-2.675.733.962-.576 1.7-1.49 2.048-2.578-.9.534-1.897.922-2.958 1.13-.85-.904-2.06-1.47-3.4-1.47-2.572 0-4.658 2.086-4.658 4.66 0 .364.042.718.12 1.06-3.873-.195-7.304-2.05-9.602-4.868-.4.69-.63 1.49-.63 2.342 0 1.616.823 3.043 2.072 3.878-.764-.025-1.482-.234-2.11-.583v.06c0 2.257 1.605 4.14 3.737 4.568-.392.106-.803.162-1.227.162-.3 0-.593-.028-.877-.082.593 1.85 2.313 3.198 4.352 3.234-1.595 1.25-3.604 1.995-5.786 1.995-.376 0-.747-.022-1.112-.065 2.062 1.323 4.51 2.093 7.14 2.093 8.57 0 13.255-7.098 13.255-13.254 0-.2-.005-.402-.014-.602.91-.658 1.7-1.477 2.323-2.41z"/>
  </svg>
);

const GithubIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path fillRule="evenodd" clipRule="evenodd" d="M12 0C5.373 0 0 5.373 0 12c0 5.303 3.438 9.8 8.207 11.387.6.113.793-.26.793-.577 0-.285-.01-1.04-.016-2.04-3.338.725-4.043-1.61-4.043-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.09-.744.083-.729.083-.729 1.205.084 1.84 1.238 1.84 1.238 1.07 1.834 2.807 1.304 3.492.997.108-.775.42-1.305.762-1.605-2.665-.303-5.467-1.334-5.467-5.93 0-1.31.468-2.38 1.235-3.22-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23a11.5 11.5 0 013.003-.404c1.02.005 2.047.138 3.006.404 2.29-1.552 3.297-1.23 3.297-1.23.653 1.652.242 2.873.12 3.176.77.84 1.234 1.91 1.234 3.22 0 4.61-2.807 5.624-5.48 5.92.432.372.816 1.103.816 2.222 0 1.604-.015 2.898-.015 3.293 0 .32.192.694.8.576C20.565 21.795 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
  </svg>
);

const LinkedinIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
  </svg>
);

interface FooterProps {
  onNavigate: (sectionId: string) => void;
}

export default function Footer({ onNavigate }: FooterProps) {
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

  const handleLinkClick = (e: React.MouseEvent, sectionId: string) => {
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