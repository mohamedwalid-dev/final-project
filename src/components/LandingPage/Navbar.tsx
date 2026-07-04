import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Menu, X, Hexagon, Sparkles, LogIn, ArrowRight } from "lucide-react";

interface NavbarProps {
  onNavigate: (sectionId: string) => void;
  activeSection: string;
}

export default function Navbar({ onNavigate, activeSection }: NavbarProps) {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 20) {
        setIsScrolled(true);
      } else {
        setIsScrolled(false);
      }
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navItems = [
    { id: "home", label: "Home" },
    { id: "features", label: "Features" },
    { id: "modules", label: "Modules" },
    { id: "analytics", label: "Analytics" },
    { id: "faq", label: "FAQ" },
    { id: "contact", label: "Contact" }
  ];

  const handleItemClick = (id: string) => {
    onNavigate(id);
    setIsMobileMenuOpen(false);
  };

  return (
    <nav
      id="main-navbar"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isScrolled
          ? "bg-white/70 backdrop-blur-xl border-b border-white/50 py-3 shadow-lg shadow-slate-100/20"
          : "bg-transparent py-5"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div
            id="nav-logo"
            className="flex items-center gap-2 cursor-pointer group"
            onClick={() => handleItemClick("home")}
          >
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 p-0.5 shadow-md shadow-blue-500/20 group-hover:scale-105 transition-transform">
              <Hexagon className="w-5 h-5 text-white fill-white/10" />
              <div className="absolute -top-1 -right-1">
                <Sparkles className="w-3 h-3 text-cyan-300 animate-pulse" />
              </div>
            </div>
            <span className="font-sans font-bold text-xl tracking-tight text-slate-900 flex items-center gap-1.5">
              Prime
            </span>
          </div>

          {/* Desktop Menu */}
          <div className="hidden lg:flex items-center gap-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                id={`nav-item-${item.id}`}
                onClick={() => handleItemClick(item.id)}
                className={`relative px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                  activeSection === item.id
                    ? "text-blue-600"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {item.label}
                {activeSection === item.id && (
                  <motion.div
                    layoutId="activeNavIndicator"
                    className="absolute bottom-0 left-4 right-4 h-0.5 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-full"
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
              </button>
            ))}
          </div>

          {/* Buttons */}
          <div className="hidden lg:flex items-center gap-4">
            <button
              id="btn-login"
              onClick={() => window.location.href = "/login"}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
            >
              <LogIn className="w-4 h-4" />
              Login
            </button>
            <button
              id="btn-get-started"
              onClick={() => window.location.href = "/login"}
              className="relative px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-md shadow-blue-600/20 transition-all hover:shadow-lg hover:shadow-blue-600/30 active:scale-98 cursor-pointer overflow-hidden group"
            >
              <span className="relative z-10 flex items-center gap-1">
                Get Started
                <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </span>
              <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </button>
          </div>

          {/* Mobile menu button */}
          <div className="flex lg:hidden items-center gap-2">
            <button
              id="btn-mobile-menu"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100/60 transition-colors"
              aria-label="Toggle Menu"
            >
              {isMobileMenuOpen ? (
                <X className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            id="mobile-navigation-panel"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="lg:hidden bg-white/95 backdrop-blur-md border-b border-slate-200 overflow-hidden"
          >
            <div className="px-4 pt-2 pb-6 space-y-2">
              {navItems.map((item) => (
                <button
                  key={item.id}
                  id={`nav-item-mobile-${item.id}`}
                  onClick={() => handleItemClick(item.id)}
                  className={`w-full text-left px-4 py-2.5 rounded-xl text-base font-medium transition-colors flex items-center ${
                    activeSection === item.id
                      ? "bg-blue-50/80 text-blue-600"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  {item.label}
                </button>
              ))}
              <div className="pt-4 border-t border-slate-250 flex flex-col gap-3 px-4">
                <button
                  id="btn-mobile-login"
                  onClick={() => window.location.href = "/login"}
                  className="flex items-center justify-center gap-2 py-3 rounded-xl text-base font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors"
                >
                  <LogIn className="w-4 h-4" />
                  Login
                </button>
                <button
                  id="btn-mobile-get-started"
                  onClick={() => window.location.href = "/login"}
                  className="w-full py-3 rounded-xl text-center font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 flex items-center justify-center gap-1"
                >
                  Get Started
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
