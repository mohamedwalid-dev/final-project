// ─── components/HR/SmartHRPanel.jsx ──────────────────────────────────────────
// Drop-in sidebar panel. Add to HRPage.jsx sidebarPanel section:
//
//   import SmartHRPanel from "../components/HR/SmartHRPanel";
//   // inside <div className={s.sidebarPanel}> add:
//   <SmartHRPanel employees={employees} />

import { useState } from "react";
import AILeaveModal      from "./AILeaveModal";
import AISalaryModal     from "./AISalaryModal";
import AIIncentivesModal from "./AIIncentivesModal";
import AIAbsenceModal    from "./AIAbsenceModal";
import p from "./SmartHRPanel.module.css";
import { Banknote, CalendarX, Globe2, Trophy } from "lucide-react";

const CARDS = [
  {
    key:    "leave",
    icon:   CalendarX,
    title:  "HR - Smart Leaves",
    desc:   "Optimize time-off approvals with predictive scheduling.",
    btn:    "Request AI Leave Review",
    grad:   "linear-gradient(135deg, #1a3a5c 0%, #0d2035 100%)",
    accent: "#4DABF7",
    pattern: `radial-gradient(circle at 80% 20%, rgba(77,171,247,0.15) 0%, transparent 50%),
              radial-gradient(circle at 20% 80%, rgba(59,91,219,0.1) 0%, transparent 50%)`,
  },
  {
    key:    "salary",
    icon:   Banknote,
    title:  "HR - Salary Reviews",
    desc:   "Market-indexed, performance-based compensation analysis.",
    btn:    "Request AI Salary Analysis",
    grad:   "linear-gradient(135deg, #1a2a1a 0%, #0d1f0d 100%)",
    accent: "#69DB7C",
    pattern: `radial-gradient(circle at 70% 30%, rgba(105,219,124,0.15) 0%, transparent 50%),
              radial-gradient(circle at 30% 70%, rgba(47,158,68,0.1) 0%, transparent 50%)`,
  },
  {
    key:    "incentive",
    icon:   Trophy,
    title:  "HR - Incentive Designer",
    desc:   "Create data-driven, motivating reward programs.",
    btn:    "Design Incentive Plan",
    grad:   "linear-gradient(135deg, #2a1a3a 0%, #1a0d2a 100%)",
    accent: "#CC5DE8",
    pattern: `radial-gradient(circle at 75% 25%, rgba(204,93,232,0.15) 0%, transparent 50%),
              radial-gradient(circle at 25% 75%, rgba(132,94,247,0.1) 0%, transparent 50%)`,
  },
  {
    key:    "absence",
    icon:   Globe2,
    title:  "HR - Absence Intelligence",
    desc:   "Identify and proactively manage chronic absenteeism.",
    btn:    "Analyze Absence Trends",
    grad:   "linear-gradient(135deg, #2a1a1a 0%, #1f0d0d 100%)",
    accent: "#FF8787",
    pattern: `radial-gradient(circle at 65% 35%, rgba(255,135,135,0.15) 0%, transparent 50%),
              radial-gradient(circle at 35% 65%, rgba(250,82,82,0.1) 0%, transparent 50%)`,
  },
];

export default function SmartHRPanel({ employees = [] }) {
  const [openModal, setOpenModal] = useState(null); // "leave"|"salary"|"incentive"|"absence"

  return (
    <>
      <div className={p.panel}>
        <div className={p.panelHeader}>
          <span className={p.aiDot} />
          <span className={p.panelTitle}>Smart HR Operations Center</span>
        </div>

        <div className={p.cards}>
          {CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <div key={card.key} className={p.card} style={{ "--accent": card.accent }}>
                <div className={p.cardContent}>
                  <div className={p.cardTop}>
                    <div className={p.cardIcon} style={{ background: `${card.accent}16`, border: `1px solid ${card.accent}30` }}>
                      <Icon className={p.cardIconSvg} aria-hidden="true" />
                    </div>
                    <div className={p.cardText}>
                      <p className={p.cardTitle}>{card.title}</p>
                      <p className={p.cardDesc}>{card.desc}</p>
                    </div>
                  </div>
                  <button
                    className={p.cardBtn}
                    style={{ "--accent": card.accent }}
                    onClick={() => setOpenModal(card.key)}
                  >
                    {card.btn}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Modals */}
      <AILeaveModal
        isOpen={openModal === "leave"}
        onClose={() => setOpenModal(null)}
        employees={employees}
      />
      <AISalaryModal
        isOpen={openModal === "salary"}
        onClose={() => setOpenModal(null)}
        employees={employees}
      />
      <AIIncentivesModal
        isOpen={openModal === "incentive"}
        onClose={() => setOpenModal(null)}
        employees={employees}
      />
      <AIAbsenceModal
        isOpen={openModal === "absence"}
        onClose={() => setOpenModal(null)}
        employees={employees}
      />
    </>
  );
}
