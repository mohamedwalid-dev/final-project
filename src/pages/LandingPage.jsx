import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Navbar from "../components/LandingPage/Navbar.jsx";
import Hero from "../components/LandingPage/Hero.jsx";
import TrustedCompanies from "../components/LandingPage/TrustedCompanies.jsx";
import Features from "../components/LandingPage/Features.jsx";
import AISection from "../components/LandingPage/AISection.jsx";
import ERPModules from "../components/LandingPage/ERPModules.jsx";
import DashboardPreview from "../components/LandingPage/DashboardPreview.jsx";
import Benefits from "../components/LandingPage/Benefits.jsx";
import HowItWorks from "../components/LandingPage/HowItWorks.jsx";
import Statistics from "../components/LandingPage/Statistics.jsx";
import Testimonials from "../components/LandingPage/Testimonials.jsx";
import FAQ from "../components/LandingPage/FAQ.jsx";
import CallToAction from "../components/LandingPage/CallToAction.jsx";
import Footer from "../components/LandingPage/Footer.jsx";

export default function LandingPage() {
  const [activeSection, setActiveSection] = useState("home");

  // Track scroll position to update active navbar element
  useEffect(() => {
    const sections = ["home", "features", "modules", "analytics", "why-us", "faq", "contact"];
    
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 200; // Offset

      for (const section of sections) {
        const el = document.getElementById(section);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollPosition >= top && scrollPosition < top + height) {
            setActiveSection(section);
            break;
          }
        }
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleNavigate = (sectionId) => {
    setActiveSection(sectionId);
    const target = document.getElementById(sectionId);
    if (target) {
      window.scrollTo({
        top: target.offsetTop - 85, // Navbar offset height
        behavior: "smooth"
      });
    }
  };

  return (
    <div id="landing-page-root" className="min-h-screen bg-[#F8FAFC] font-sans text-slate-900 overflow-x-hidden antialiased">
      {/* Background Orbs */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute top-[-100px] right-[-100px] w-96 h-96 bg-blue-200/40 rounded-full blur-[100px] pointer-events-none"></div>
        <div className="absolute bottom-[-100px] left-[-100px] w-96 h-96 bg-indigo-200/40 rounded-full blur-[100px] pointer-events-none"></div>
      </div>

      {/* Sticky Header Navigation */}
      <Navbar onNavigate={handleNavigate} activeSection={activeSection} />

      {/* Main Sections flow */}
      <main className="relative z-10">
        
        {/* Hero split layout */}
        <Hero />

        {/* Brand ribbon */}
        <TrustedCompanies />

        {/* 8 Features grid */}
        <Features />

        {/* Interactive AI assistant widget and bullet points */}
        <AISection />

        {/* ERP consolidated modules selectors & panels */}
        <ERPModules />

        {/* Full-size detailed ERP sandbox console charts */}
        <DashboardPreview />

        {/* Timeline benefits: why us */}
        <Benefits />

        {/* Counters statistics indicators */}
        <Statistics />

        {/* Three step timeline workflow cards */}
        <HowItWorks />

        {/* Rating cards grid / carousel */}
        <Testimonials />

        {/* Accordions FAQs */}
        <FAQ />

        {/* Lead capture banner */}
        <CallToAction />

      </main>

      {/* Global standard footer */}
      <Footer onNavigate={handleNavigate} />
    </div>
  );
}

