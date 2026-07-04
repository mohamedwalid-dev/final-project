import React from "react";
import { Hexagon, Sparkles, Twitter, Github, Linkedin, MessageSquare, Globe, Mail, PhoneCall } from "lucide-react";

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
              <Twitter className="w-4 h-4" />
            </a>
            <a href="#" onClick={(e) => e.preventDefault()} className="hover:text-slate-900 hover:bg-slate-50 p-2 rounded-lg bg-white border border-slate-200 shadow-sm transition-colors" aria-label="Github repository link">
              <Github className="w-4 h-4" />
            </a>
            <a href="#" onClick={(e) => e.preventDefault()} className="hover:text-slate-900 hover:bg-slate-50 p-2 rounded-lg bg-white border border-slate-200 shadow-sm transition-colors" aria-label="LinkedIn profile link">
              <Linkedin className="w-4 h-4" />
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
