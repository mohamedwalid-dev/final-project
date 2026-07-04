// ─── Pages/DesignSystemPage.jsx ───────────────────────────────────────────────
// ✅ Color Palette, Typography Scale, Buttons & Interactions
// ✅ Form Elements, Elevation & Cards, Tables & Tabs
// ✅ Responsive Logic sub-view, States & Feedback
// ✅ Right-side Table of Contents, animations throughout

import { useState, useEffect, useRef, useCallback } from "react";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";
import s from "../styles/DesignSystemPage.module.css";
import shell from "../styles/AppShell.module.css";

// ─── DATA ────────────────────────────────────────────────────────────────────
const COLORS = [
  { name: "Primary",    hex: "#3B5BDB", text: "#fff" },
  { name: "Secondary",  hex: "#7048E8", text: "#fff" },
  { name: "Surface",    hex: "#F8F9FC", text: "#374151" },
  { name: "Background", hex: "#FFFFFF", text: "#374151", border: true },
  { name: "Card",       hex: "#FFFFFF", text: "#374151", border: true },
  { name: "Border",     hex: "#E2E8F0", text: "#374151" },
];
const SEMANTIC_COLORS = [
  { name: "Success",      hex: "#2F9E44", text: "#fff" },
  { name: "Black",        hex: "#1A202C", text: "#fff" },
  { name: "Inactive",     hex: "#9CA3AF", text: "#fff" },
  { name: "Warning",      hex: "#F59F00", text: "#fff" },
  { name: "Destructive",  hex: "#FA5252", text: "#fff" },
  { name: "Info",         hex: "#0EA5E9", text: "#fff" },
];

const TYPE_SCALE = [
  { label: "Display / H1",    size: "48px", weight: 800, sample: "The quick brown fox",            lh: "1.1" },
  { label: "Heading / H2",    size: "32px", weight: 700, sample: "Jumps over the lazy dog",        lh: "1.2" },
  { label: "Title / H3",      size: "24px", weight: 700, sample: "Quality analytics at your fingertips", lh: "1.3" },
  { label: "Body / Large",    size: "16px", weight: 400, sample: "Our ERP system focuses on clarity and efficiency providing users with the data they need to manage complex enterprise workflows.", lh: "1.6" },
  { label: "Body / Small",    size: "13px", weight: 400, sample: "Require me to translate analytics, descriptions, and user inputs. Generate to unique sentences that capture Prime complex enterprise workflows and data sets.", lh: "1.6" },
  { label: "Mono / Code",     size: "13px", weight: 400, sample: "Prime-PRO-2024-X0GL",          lh: "1.5", mono: true },
];

const TABLE_DATA = [
  { id:"TX-1001", customer:"Acme Corporation",    date:"Oct 01, 2024", amount:"EGP 12,400.00", status:"Paid",     risk:"Low" },
  { id:"TX-1002", customer:"Fontaine Dynamics",   date:"Oct 08, 2024", amount:"EGP 34,250.00", status:"Pending",  risk:"Med" },
  { id:"TX-1003", customer:"Blue Meridian Co.",   date:"Oct 12, 2024", amount:"EGP 8,700.00",  status:"Overdue",  risk:"High"},
  { id:"TX-1004", customer:"Stellar Manufacturing",date:"Oct 20, 2024", amount:"EGP 29,500.00", status:"Paid",    risk:"Low" },
  { id:"TX-1005", customer:"Vertex Systems",      date:"Oct 25, 2024", amount:"EGP 5,200.00",  status:"Paid",     risk:"Low" },
];

const FAQ = [
  { q: "What is Prime Cloud Integration?",   a: "Prime Cloud Integration connects your ERP data seamlessly with third-party cloud solutions via our open API ecosystem." },
  { q: "Is your comfort mode available online?", a: "Yes! Prime's comfort mode is available across all browsers and adapts to your system's dark/light preference automatically." },
];

const RESPONSIVE_MODULES = [
  { id: "dashboard", icon: "⊞", label: "Executive Dashboard", desc: "KPI cards & Analytics",    active: true  },
  { id: "invoices",  icon: "📄", label: "Invoices List",        desc: "Data tables & Statuses",   active: false },
  { id: "hr",        icon: "👥", label: "Employee Grid",        desc: "Staff directory & Profiles",active: false },
  { id: "sales",     icon: "◎", label: "Leads Kanban",          desc: "CRM Pipeline cards",       active: false },
  { id: "support",   icon: "🎫", label: "Tickets System",       desc: "Messaging & SLAs",         active: false },
];

const TOC = [
  { id: "colors",     label: "Color Palette" },
  { id: "typography", label: "Typography Scale" },
  { id: "buttons",    label: "Buttons & Interactions" },
  { id: "forms",      label: "Form Elements" },
  { id: "elevation",  label: "Elevation & Cards" },
  { id: "tables",     label: "Organisms: Tables & Tabs" },
  { id: "responsive", label: "Responsive Logic" },
  { id: "states",     label: "States & Feedback" },
];

const STATUS_META = {
  Paid:    { bg: "#EBFBEE", color: "#2F9E44" },
  Pending: { bg: "#FFF9DB", color: "#E67700" },
  Overdue: { bg: "#FFE3E3", color: "#C92A2A" },
};
const RISK_META = {
  Low:  { bg: "#EBFBEE", color: "#2F9E44" },
  Med:  { bg: "#FFF9DB", color: "#E67700" },
  High: { bg: "#FFE3E3", color: "#C92A2A" },
};

function useAnimateIn(delay = 0) {
  const [v, setV] = useState(false);
  useEffect(() => { const t = setTimeout(() => setV(true), delay); return () => clearTimeout(t); }, [delay]);
  return { style: { opacity: v ? 1 : 0, transform: v ? "translateY(0)" : "translateY(18px)", transition: `opacity 0.45s ease ${delay}ms, transform 0.45s ease ${delay}ms` } };
}

function useCopied() {
  const [copied, setCopied] = useState(null);
  const copy = useCallback((text) => {
    navigator.clipboard?.writeText(text).catch(() => {});
    setCopied(text);
    setTimeout(() => setCopied(null), 1600);
  }, []);
  return [copied, copy];
}

// ─── COLOR SWATCH ────────────────────────────────────────────────────────────
function Swatch({ name, hex, text, border, copied, onCopy }) {
  const iscopied = copied === hex;
  return (
    <div className={s.swatch} onClick={() => onCopy(hex)} title={`Copy ${hex}`}>
      <div className={s.swatchColor} style={{ background: hex, border: border ? "1.5px solid #E2E8F0" : undefined }}>
        {iscopied && <span className={s.copiedBadge}>✓ Copied</span>}
      </div>
      <p className={s.swatchName}>{name}</p>
      <p className={s.swatchHex}>{hex}</p>
    </div>
  );
}

// ─── SECTION WRAPPER ─────────────────────────────────────────────────────────
function Section({ id, title, desc, children, delay = 0 }) {
  const anim = useAnimateIn(delay);
  return (
    <section id={id} className={s.section} style={anim.style}>
      <div className={s.sectionHeader}>
        <h2 className={s.sectionTitle}>{title}</h2>
        {desc && <p className={s.sectionDesc}>{desc}</p>}
      </div>
      {children}
    </section>
  );
}

// ─── RESPONSIVE LOGIC SUB-VIEW ───────────────────────────────────────────────
function ResponsiveLogic() {
  const [active, setActive] = useState("dashboard");
  return (
    <div className={s.responsiveWrap}>
      {/* Module picker */}
      <div className={s.moduleRow}>
        {RESPONSIVE_MODULES.map((m) => (
          <button
            key={m.id}
            className={`${s.moduleCard} ${active === m.id ? s.moduleCardActive : ""}`}
            onClick={() => setActive(m.id)}
          >
            <span className={s.moduleIcon}>{m.icon}</span>
            <p className={s.moduleLabel}>{m.label}</p>
            <p className={s.moduleDesc}>{m.desc}</p>
            {active === m.id && <span className={s.moduleActiveBadge}>ACTIVE PREVIEW →</span>}
          </button>
        ))}
      </div>

      {/* Viewport previews */}
      <div className={s.viewportRow}>
        {/* Tablet */}
        <div className={s.viewportBox}>
          <div className={s.viewportLabel}><span className={s.vpIcon}>⬜</span> Tablet Viewport <span className={s.vpSize}>768 × 1024</span></div>
          <div className={s.deviceFrame}>
            <div className={s.deviceNav}><span>≡</span><span className={s.deviceNavTitle}>Analytics</span><span className={s.deviceNavAvatar}>AS</span></div>
            <div className={s.deviceContent}>
              <div className={s.deviceCardRow}>
                <div className={s.deviceCard} style={{ background: "linear-gradient(135deg,#EEF2FF,#C5D0FC)" }}>
                  <p className={s.dcLabel}>Monthly Revenue</p>
                  <p className={s.dcValue}>EGP 42,950</p>
                  <p className={s.dcDelta}>↑ +13.8% from last month</p>
                </div>
                <div className={s.deviceCard}>
                  <p className={s.dcLabel}>Active Projects</p>
                  <p className={s.dcValue}>24</p>
                  <div className={s.dcBar}><div className={s.dcBarFill} style={{ width: "60%", background: "#3B5BDB" }}/></div>
                </div>
              </div>
              <p className={s.dcSection}>Profit Trends</p>
              <div className={s.dcChart}>{[40,70,55,90,65,80,48].map((h,i) => <div key={i} className={s.dcBar2} style={{ height: h+"%" }}/>)}</div>
              <p className={s.dcSection}>Recent Transactions <span style={{ float:"right", color:"#3B5BDB", fontSize:11 }}>View all</span></p>
              {["Software License #1021","Software License #1022","Software License #1023"].map((t,i) => (
                <div key={i} className={s.dcTx}><span className={s.dcTxIcon}>📄</span><div><p className={s.dcTxName}>{t}</p><p className={s.dcTxSub}>Subscription Payment</p></div><span className={s.dcTxAmt}>-EGP 299.00</span></div>
              ))}
            </div>
          </div>
          <div className={s.adaptiveLogic}>
            <p className={s.alTitle}>■ Adaptive Logic: Tablet</p>
            <div className={s.alRow}>
              <div><p className={s.alLabel}>Navigation</p><p className={s.alText}>Sidebar collapses into a hidden sheet menu triggered by the hamburger icon.</p></div>
              <div><p className={s.alLabel}>Density</p><p className={s.alText}>Main grid shifts to 2-columns. KPIs maintain horizontal layout but smaller margins.</p></div>
            </div>
          </div>
        </div>

        {/* Mobile */}
        <div className={s.viewportBox}>
          <div className={s.viewportLabel}><span className={s.vpIcon}>📱</span> Mobile Viewport <span className={s.vpSize}>375 × 812</span></div>
          <div className={`${s.deviceFrame} ${s.deviceFrameMobile}`}>
            <div className={s.deviceNav}><span className={s.deviceNavTitle}>Analytics</span><span className={s.deviceNavAvatar}>AS</span></div>
            <div className={s.deviceContent}>
              <div className={s.deviceCard} style={{ background: "linear-gradient(135deg,#EEF2FF,#C5D0FC)", marginBottom: 8 }}>
                <p className={s.dcLabel}>Monthly Revenue</p>
                <p className={s.dcValue}>EGP 42,950</p>
                <p className={s.dcDelta}>↑ +13.8% from last month</p>
              </div>
              <div className={s.deviceCard} style={{ marginBottom: 8 }}>
                <p className={s.dcLabel}>Active Projects</p>
                <p className={s.dcValue}>24</p>
                <div className={s.dcBar}><div className={s.dcBarFill} style={{ width: "60%", background: "#3B5BDB" }}/></div>
              </div>
              <p className={s.dcSection}>Profit Trends</p>
              <div className={s.dcChart} style={{ height: 60 }}>{[40,70,55,90,65,80,48].map((h,i) => <div key={i} className={s.dcBar2} style={{ height: h+"%" }}/>)}</div>
              <p className={s.dcSection}>Recent Transactions <span style={{ float:"right", color:"#3B5BDB", fontSize:10 }}>View all</span></p>
              {["Software License #1021","Software License #1022"].map((t,i) => (
                <div key={i} className={s.dcTx}><span className={s.dcTxIcon}>📄</span><div><p className={s.dcTxName}>{t}</p></div><span className={s.dcTxAmt}>-EGP 299.00</span></div>
              ))}
              <div className={s.mobileTabBar}>{["🏠","📄","👥","◎","•••"].map((ic,i) => <button key={i} className={`${s.mobileTab} ${i===0?s.mobileTabActive:""}`}>{ic}</button>)}</div>
            </div>
          </div>
          <div className={s.adaptiveLogic}>
            <p className={s.alTitle}>■ Adaptive Logic: Mobile</p>
            <div className={s.alRow}>
              <div><p className={s.alLabel}>Navigation</p><p className={s.alText}>Sidebar is replaced by a high-accessibility Bottom Tab Bar for core modules.</p></div>
              <div><p className={s.alLabel}>Content Flow</p><p className={s.alText}>All grids stack vertically (1-column). Charts become scrollable or simplified.</p></div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer links */}
      <div className={s.responsiveFooter}>
        <div className={s.rfCard}>
          <p className={s.rfIcon}>⬇</p>
          <p className={s.rfTitle}>Export Spec</p>
          <p className={s.rfDesc}>Download the Figma responsive tokens for direct handoff to engineering teams.</p>
          <button className={s.rfLink}>Download Tokens (.json) →</button>
        </div>
        <div className={s.rfCard}>
          <p className={s.rfIcon}>Aa</p>
          <p className={s.rfTitle}>Fluid Typography</p>
          <p className={s.rfDesc}>Headings scale automatically using a 1.25 ratio across breakpoints for perfect readability.</p>
          <button className={s.rfLink}>View Type Scale →</button>
        </div>
        <div className={s.rfCard}>
          <p className={s.rfIcon}>▽</p>
          <p className={s.rfTitle}>Auto-Hide Logic</p>
          <p className={s.rfDesc}>Secondary filters and bulk actions are moved to a floating sheet menu on small screens.</p>
          <button className={s.rfLink}>Read Documentation →</button>
        </div>
      </div>
    </div>
  );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function DesignSystemPage() {
  const [activeNav,   setActiveNav]   = useState("design");
  const [tab,         setTab]         = useState("components");
  const [toggle,      setToggle]      = useState(true);
  const [slider,      setSlider]      = useState(72);
  const [checkboxA,   setCheckboxA]   = useState(true);
  const [checkboxB,   setCheckboxB]   = useState(false);
  const [faqOpen,     setFaqOpen]     = useState({});
  const [activeTab,   setActiveTab]   = useState("transactions");
  const [activeSection, setActiveSection] = useState("colors");
  const [copied, onCopy] = useCopied();
  const [toast, setToast] = useState(null);
  const headerAnim = useAnimateIn(0);

  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  }, []);

  // Scroll spy
  useEffect(() => {
    const handleScroll = () => {
      const sections = TOC.map(t => document.getElementById(t.id));
      for (const sec of [...sections].reverse()) {
        if (sec && sec.getBoundingClientRect().top <= 120) {
          setActiveSection(sec.id);
          break;
        }
      }
    };
    const el = document.getElementById("ds-scroll");
    el?.addEventListener("scroll", handleScroll);
    return () => el?.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSection(id);
  };

  return (
    <>
      <style>{`
        @keyframes modalIn{from{opacity:0;transform:scale(0.95) translateY(10px)}to{opacity:1;transform:scale(1) translateY(0)}}
        @keyframes toastIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
        *{box-sizing:border-box}
      `}</style>

      <div className={shell.appShell}>
        <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
        <div className={shell.mainArea}>
          <Header breadcrumbs={["Prime ERP", "Design System", tab === "responsive" ? "Responsive Variants" : "Components"]} />
          <main className={s.page} id="ds-scroll">

            {/* Toast */}
            {toast && <div className={s.toast}>{toast}</div>}

            <div className={s.layout}>

              {/* ── MAIN CONTENT ── */}
              <div className={s.content}>

                {/* Page Header */}
                <div className={s.pageHeader} style={headerAnim.style}>
                  <div>
                    <div className={s.pageTag}>✦ Prime DESIGN SYSTEM</div>
                    <h1 className={s.pageTitle}>{tab === "responsive" ? "Responsive Logic" : "Prime Design System"}</h1>
                    <p className={s.pageSub}>
                      {tab === "responsive"
                        ? "See how Prime components adapt from desktop-first structures to fluid mobile-first layouts."
                        : "A comprehensive collection of design tokens, interactive components, and visual patterns that power the Prime ERP ecosystem."}
                    </p>
                  </div>
                  <div className={s.headerActions}>
                    <button className={s.btnOutline} onClick={() => showToast("📋 Design tokens copied!")}>⬇ Export Tokens</button>
                    <button className={s.btnPrimary} onClick={() => showToast("📐 Figma file opened!")}>📐 Open in Figma</button>
                  </div>
                </div>

                {/* Top Tabs */}
                <div className={s.topTabs}>
                  {[["components","Components"],["responsive","Responsive Variants"],["tokens","Design Tokens"],["icons","Icon Library"]].map(([key,label]) => (
                    <button key={key} className={`${s.topTab} ${tab===key?s.topTabActive:""}`} onClick={() => setTab(key)}>{label}</button>
                  ))}
                </div>

                {/* ──── COMPONENTS TAB ──── */}
                {tab === "components" && (
                  <>
                    {/* ── Color Palette ── */}
                    <Section id="colors" title="Color Palette" delay={50}
                      desc="A comprehensive set of brand colors and accessibility-tested UI palette variables for Prime forms. We utilize CSS variables for dynamic theme switching.">
                      <div className={s.swatchRow}>
                        {COLORS.map(c => <Swatch key={c.name} {...c} copied={copied} onCopy={onCopy} />)}
                      </div>
                      <div className={s.swatchRow} style={{ marginTop: 12 }}>
                        {SEMANTIC_COLORS.map(c => <Swatch key={c.name} {...c} copied={copied} onCopy={onCopy} />)}
                      </div>
                    </Section>

                    {/* ── Typography ── */}
                    <Section id="typography" title="Typography Scale" delay={100}
                      desc="We use DM Sans (selected and most workload optimized for readability in data-heavy performance). Ibis Sans was used for frontends.">
                      <div className={s.typeList}>
                        {TYPE_SCALE.map((t, i) => (
                          <div key={i} className={s.typeRow}>
                            <div className={s.typeMeta}>
                              <span className={s.typeLabel}>{t.label}</span>
                              <span className={s.typeProp}>{t.size} · {t.weight > 500 ? "Bold" : "Regular"} · LH {t.lh}</span>
                            </div>
                            <p className={s.typeSample} style={{ fontSize: t.size, fontWeight: t.weight, fontFamily: t.mono ? "'Fira Code',monospace" : undefined, lineHeight: t.lh, maxWidth: "100%" }}>
                              {t.sample}
                            </p>
                          </div>
                        ))}
                      </div>
                    </Section>

                    {/* ── Buttons ── */}
                    <Section id="buttons" title="Buttons & Interactions" delay={150}
                      desc="Buttons can perform entire button clicks. They can fill and solidify gradient transitions for each interaction state.">
                      <div className={s.btnShowcase}>
                        <div className={s.btnGroup}>
                          <p className={s.showcaseLabel}>PRIMARY & VARIANTS</p>
                          <div className={s.btnRow}>
                            <button className={`${s.btn} ${s.btnPrimary}`}>Primary Button</button>
                            <button className={`${s.btn} ${s.btnSecondary}`}>Secondary</button>
                            <button className={`${s.btn} ${s.btnPrimary} ${s.btnSm}`}>Small</button>
                            <button className={`${s.btn} ${s.btnPrimary} ${s.btnLg}`}>Large Button</button>
                          </div>
                          <div className={s.btnRow} style={{ marginTop: 10 }}>
                            <button className={`${s.btn} ${s.btnPrimary}`} disabled>Disabled</button>
                            <button className={`${s.btn} ${s.btnDanger}`}>Delete Action</button>
                            <button className={`${s.btn} ${s.btnPrimary}`}><span className={s.spinner} /> Loading…</button>
                          </div>
                        </div>
                        <div className={s.btnGroup}>
                          <p className={s.showcaseLabel}>COLORS & SIZES</p>
                          <div className={s.btnRow}>
                            <button className={`${s.btn} ${s.btnGhost}`}>Ghost</button>
                            <button className={`${s.btn} ${s.btnOutline}`}>Outline</button>
                            <button className={`${s.btn} ${s.btnSuccess}`}>Confirm</button>
                            <button className={`${s.btn} ${s.btnWarning}`}>Warn</button>
                          </div>
                          <div className={s.btnRow} style={{ marginTop: 10 }}>
                            <button className={`${s.btn} ${s.btnPrimary}`} onClick={() => showToast("✅ Action confirmed!")}>+ New Item</button>
                            <button className={`${s.btn} ${s.btnDanger}`} onClick={() => showToast("🗑 Item deleted!")}>⛔ Delete</button>
                          </div>
                        </div>
                      </div>
                    </Section>

                    {/* ── Form Elements ── */}
                    <Section id="forms" title="Form Elements" delay={200}
                      desc="Seamlessly crafted input fields, validating user-controlled value scrolls and operators.">
                      <div className={s.formShowcase}>
                        <div className={s.formCol}>
                          <div className={s.formGroup}>
                            <label className={s.formLabel}>Email Address</label>
                            <input className={s.formInput} placeholder="user@Prime.io" defaultValue="alex@Prime.io" />
                            <p className={s.formHint}>This field is connected to your primary account.</p>
                          </div>
                          <div className={s.formGroup}>
                            <label className={s.formLabel}>Invalid Entry</label>
                            <input className={`${s.formInput} ${s.formInputError}`} placeholder="Invalid value" defaultValue="bad-value@" />
                            <p className={s.formError}>✕ This email format is not recognized.</p>
                          </div>
                          <div className={s.formGroup}>
                            <label className={s.formLabel}>Country / Locale</label>
                            <select className={s.formSelect}>
                              <option>United States</option>
                              <option>Egypt</option>
                              <option>United Kingdom</option>
                              <option>Germany</option>
                            </select>
                          </div>
                        </div>
                        <div className={s.formCol}>
                          <div className={s.formGroup}>
                            <label className={s.formLabel}>Current Notifications</label>
                            <div className={s.toggleRow}>
                              <span className={s.toggleLabel}>Email notifications enabled</span>
                              <button className={`${s.toggle} ${toggle ? s.toggleOn : ""}`} onClick={() => setToggle(p=>!p)}>
                                <span className={s.toggleKnob} />
                              </button>
                            </div>
                            <div className={s.toggleRow}>
                              <span className={s.toggleLabel}>SMS alerts</span>
                              <button className={`${s.toggle}`}>
                                <span className={s.toggleKnob} />
                              </button>
                            </div>
                          </div>
                          <div className={s.formGroup}>
                            <label className={s.formLabel}>Storage Limit <span style={{ color:"#3B5BDB",fontWeight:700 }}>{slider}%</span></label>
                            <input type="range" min={0} max={100} value={slider} onChange={e=>setSlider(+e.target.value)} className={s.slider} />
                          </div>
                          <div className={s.formGroup}>
                            <label className={s.formLabel}>Permissions</label>
                            <label className={s.checkboxRow}>
                              <input type="checkbox" checked={checkboxA} onChange={e=>setCheckboxA(e.target.checked)} className={s.checkbox} />
                              <span>☑ Agree to data processing terms</span>
                            </label>
                            <label className={s.checkboxRow}>
                              <input type="checkbox" checked={checkboxB} onChange={e=>setCheckboxB(e.target.checked)} className={s.checkbox} />
                              <span>☐ Subscribe to product updates</span>
                            </label>
                          </div>
                        </div>
                      </div>
                    </Section>

                    {/* ── Elevation & Cards ── */}
                    <Section id="elevation" title="Elevation & Cards" delay={250}
                      desc="We use shadow-spacing to define hierarchy. Background and colours to used for panel separation.">
                      <div className={s.elevationRow}>
                        {[
                          { label:"Shadow XS", shadow:"0 1px 4px rgba(0,0,0,0.07)", tag:null, text:"Shadow XS", sub:"Subtle card borders, inline widgets.", btn:"View Details" },
                          { label:"Shadow MD", shadow:"0 4px 16px rgba(0,0,0,0.12)", tag:"Recommended", text:"Shadow MD", sub:"Standard cards, panels, dropdowns.", btn:"Select Options" },
                          { label:"Shadow XL", shadow:"0 12px 36px rgba(59,91,219,0.18)", tag:"High Contrast", text:"Shadow XL", sub:"Modals, drawers, feature callouts.", btn:"Add to Cart" },
                        ].map((e,i) => (
                          <div key={i} className={s.elevCard} style={{ boxShadow: e.shadow }}>
                            {e.tag && <span className={s.elevTag} style={{ background: i===2?"#3B5BDB":"#3B5BDB" }}>{e.tag}</span>}
                            <p className={s.elevLabel}>{e.label}</p>
                            <p className={s.elevText}>{e.text}</p>
                            <p className={s.elevSub}>{e.sub}</p>
                            <button className={`${s.btn} ${i===2?s.btnPrimary:i===1?s.btnSecondary:s.btnGhost}`}>{e.btn}</button>
                          </div>
                        ))}
                      </div>
                    </Section>

                    {/* ── Tables & Tabs ── */}
                    <Section id="tables" title="Organisms: Tables & Tabs" delay={300}
                      desc="Our table and tab components use a declarative, configurable list structure with status chips, priority indicators and multiple tab indicators.">
                      {/* Sub-tabs */}
                      <div className={s.subTabs}>
                        {[["transactions","Transactions Table"],["faq","Interactive Modals"]].map(([k,l]) => (
                          <button key={k} className={`${s.subTab} ${activeTab===k?s.subTabActive:""}`} onClick={() => setActiveTab(k)}>{l}</button>
                        ))}
                      </div>

                      {activeTab === "transactions" && (
                        <div className={s.tableWrap}>
                          <table className={s.table}>
                            <thead>
                              <tr>{["Transaction ID","Customer","Date","Amount","Status","Risk"].map(h=><th key={h} className={s.th}>{h}</th>)}</tr>
                            </thead>
                            <tbody>
                              {TABLE_DATA.map(row=>(
                                <tr key={row.id} className={s.tr}>
                                  <td className={s.td}><span className={s.txId}>{row.id}</span></td>
                                  <td className={s.td}>{row.customer}</td>
                                  <td className={s.td}>{row.date}</td>
                                  <td className={s.td}><strong>{row.amount}</strong></td>
                                  <td className={s.td}>
                                    <span className={s.statusBadge} style={{ background: STATUS_META[row.status]?.bg, color: STATUS_META[row.status]?.color }}>{row.status}</span>
                                  </td>
                                  <td className={s.td}>
                                    <span className={s.riskBadge} style={{ background: RISK_META[row.risk]?.bg, color: RISK_META[row.risk]?.color }}>{row.risk}</span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          <div className={s.tablePagination}>
                            <span className={s.paginationInfo}>Showing 1–5 of 5 results</span>
                            <div className={s.paginationBtns}>
                              {[1,2,3].map(p=><button key={p} className={`${s.pageBtn} ${p===1?s.pageBtnActive:""}`}>{p}</button>)}
                            </div>
                          </div>
                        </div>
                      )}

                      {activeTab === "faq" && (
                        <div className={s.faqList}>
                          {FAQ.map((item,i) => (
                            <div key={i} className={s.faqItem}>
                              <button className={s.faqQ} onClick={() => setFaqOpen(p=>({...p,[i]:!p[i]}))}>
                                <span>{item.q}</span>
                                <span className={s.faqChevron}>{faqOpen[i]?"▲":"▼"}</span>
                              </button>
                              {faqOpen[i] && <div className={s.faqA}>{item.a}</div>}
                            </div>
                          ))}
                          <div className={s.faqModal}>
                            <div className={s.faqModalIcon}>⬜</div>
                            <p className={s.faqModalTitle}>Interactive Models</p>
                            <p className={s.faqModalSub}>Explore our interactive design tokens and component documentation.</p>
                            <button className={s.btnPrimary} style={{ fontSize:12, padding:"7px 14px", borderRadius:8 }} onClick={() => showToast("📐 Opening system rating...")}>Launch System Rating</button>
                          </div>
                        </div>
                      )}
                    </Section>

                    {/* ── States & Feedback ── */}
                    <Section id="states" title="States & Feedback" delay={350}
                      desc="Smooth handling of loading, error, and empty states delivers a seamless user experience.">
                      <div className={s.statesRow}>
                        <div className={s.stateCard}>
                          <p className={s.stateCardLabel}>Loading Skeleton</p>
                          <div className={s.skeleton} style={{ height:16,width:"80%",marginBottom:8 }}/>
                          <div className={s.skeleton} style={{ height:16,width:"60%",marginBottom:8 }}/>
                          <div className={s.skeleton} style={{ height:16,width:"70%" }}/>
                        </div>
                        <div className={s.stateCard}>
                          <p className={s.stateCardLabel}>Error State</p>
                          <div className={s.errorState}>
                            <span className={s.errorIcon}>⚠</span>
                            <p className={s.errorTitle}>Something went wrong</p>
                            <p className={s.errorSub}>We couldn't load the data. Check your connection and try again.</p>
                            <button className={`${s.btn} ${s.btnDanger}`} style={{ fontSize:12,padding:"6px 14px" }}>Retry</button>
                          </div>
                        </div>
                        <div className={s.stateCard}>
                          <p className={s.stateCardLabel}>Empty State</p>
                          <div className={s.emptyState}>
                            <span className={s.emptyIcon}>📭</span>
                            <p className={s.emptyTitle}>No Records Found</p>
                            <p className={s.emptySub}>We couldn't find anything matching your filters. Try adjusting your search or filters.</p>
                            <div style={{ display:"flex",gap:8,marginTop:10 }}>
                              <button className={`${s.btn} ${s.btnGhost}`} style={{ fontSize:12,padding:"6px 12px" }}>Reset Filters</button>
                              <button className={`${s.btn} ${s.btnPrimary}`} style={{ fontSize:12,padding:"6px 12px" }}>+ Add New</button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </Section>
                  </>
                )}

                {/* ──── RESPONSIVE TAB ──── */}
                {tab === "responsive" && (
                  <section id="responsive" className={s.section}>
                    <ResponsiveLogic />
                  </section>
                )}

                {/* ──── TOKENS TAB ──── */}
                {tab === "tokens" && (
                  <section className={s.section}>
                    <div className={s.tokensGrid}>
                      {[["--color-primary","#3B5BDB"],["--color-secondary","#7048E8"],["--color-success","#2F9E44"],["--color-danger","#FA5252"],["--color-warning","#F59F00"],["--color-surface","#F8F9FC"],["--radius-sm","8px"],["--radius-md","12px"],["--radius-lg","18px"],["--shadow-xs","0 1px 4px rgba(0,0,0,0.07)"],["--shadow-md","0 4px 16px rgba(0,0,0,0.12)"],["--shadow-xl","0 12px 36px rgba(0,0,0,0.18)"],["--font-size-display","48px"],["--font-size-body","16px"],["--spacing-sm","8px"],["--spacing-md","16px"],["--spacing-lg","24px"],["--spacing-xl","32px"]].map(([k,v]) => (
                        <div key={k} className={s.tokenCard} onClick={() => { onCopy(v); showToast(`✓ ${k} copied!`); }}>
                          <p className={s.tokenKey}>{k}</p>
                          <p className={s.tokenValue}>{v}</p>
                          {v.startsWith("#") && <div className={s.tokenColor} style={{ background:v }}/>}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* ──── ICONS TAB ──── */}
                {tab === "icons" && (
                  <section className={s.section}>
                    <div className={s.iconGrid}>
                      {["⊞","◈","👤","◎","▤","◌","✦","📦","📄","📊","⚠","🔍","🔔","💬","📞","🔐","✕","✓","▲","▼","›","‹","→","↑","↓","📎","🙂","🎫","📬","🏭","📡","⬇","📐","🗑","⛔","✏️","👁","···","🏗","📋"].map((ic,i) => (
                        <div key={i} className={s.iconCard} onClick={() => { onCopy(ic); showToast(`✓ Icon copied!`); }} title="Click to copy">
                          <span className={s.iconGlyph}>{ic}</span>
                          <span className={s.iconCode}>{ic}</span>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

              </div>

              {/* ── RIGHT TOC ── */}
              {tab === "components" && (
                <aside className={s.toc}>
                  <p className={s.tocTitle}>ON THIS PAGE</p>
                  <nav className={s.tocNav}>
                    {TOC.map(t => (
                      <button key={t.id} className={`${s.tocItem} ${activeSection===t.id?s.tocItemActive:""}`} onClick={() => scrollTo(t.id)}>
                        {t.label}
                      </button>
                    ))}
                  </nav>
                  <div className={s.tocDivider}/>
                  <p className={s.tocSub}>ALSO IN THIS SECTION</p>
                  <div className={s.tocLinks}>
                    {["Spacing System","Grid Layout","Motion Tokens","Accessibility Guide"].map(l => (
                      <button key={l} className={s.tocLink} onClick={() => showToast("📄 Coming soon!")}>{l}</button>
                    ))}
                  </div>
                  <div className={s.tocDivider}/>
                  <div className={s.tocVersion}>
                    <span className={s.tocVersionDot}/>
                    <div>
                      <p className={s.tocVersionLabel}>Design Mode Active</p>
                      <p className={s.tocVersionSub}>v2.4.0 · Stable</p>
                    </div>
                  </div>
                </aside>
              )}
            </div>

            <footer className={s.footer}>
              <span>© 2024 Prime ERP Systems. All rights reserved.</span>
              <div className={s.footerRight}>
                <a href="#" className={s.footerLink}>Privacy Policy</a>
                <a href="#" className={s.footerLink}>Terms of Service</a>
                <span className={s.statusDot}><span style={{ width:7,height:7,borderRadius:"50%",background:"#2F9E44",display:"inline-block",marginRight:5 }}/>System Status: Operational</span>
                <span>v1-stable</span>
              </div>
            </footer>
          </main>
        </div>
      </div>
    </>
  );
}
