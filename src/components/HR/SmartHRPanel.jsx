import { useState } from "react";
import AILeaveModal      from "./AILeaveModal";
import AISalaryModal     from "./AISalaryModal";
import AIIncentivesModal from "./AIIncentivesModal";
import AIAbsenceModal    from "./AIAbsenceModal";
import p from "./SmartHRPanel.module.css";

const CARDS = [
  {
    key: "leave",
    title: "HR - Smart Leaves",
    desc: "Optimize time-off approvals with predictive scheduling.",
    btn: "Request AI Leave Review",
  },
  {
    key: "salary",
    title: "HR - Salary Reviews",
    desc: "Market-indexed, performance-based compensation analysis.",
    btn: "Request AI Salary Analysis",
  },
  {
    key: "incentive",
    title: "HR - Incentive Designer",
    desc: "Create data-driven, motivating reward programs.",
    btn: "Design Incentive Plan",
  },
  {
    key: "absence",
    title: "HR - Absence Intelligence",
    desc: "Identify and proactively manage chronic absenteeism.",
    btn: "Analyze Absence Trends",
  },
];

export default function SmartHRPanel({ employees = [] }) {
  const [openModal, setOpenModal] = useState(null);

  return (
    <>
      <div className={p.panel}>

        {/* Header */}
        <div className={p.panelHeader}>
          <span className={p.aiDot} />
          <span className={p.panelTitle}>Smart HR Operations Center</span>
        </div>

        {/* Cards */}
        <div className={p.cards}>
          {CARDS.map((card) => (
            <div key={card.key} className={p.card}>

              <div className={p.cardContent}>

                <div className={p.cardTop}>
                 <div className={p.cardIconPlaceholder}></div>
                  <div className={p.cardText}>
                    <p className={p.cardTitle}>{card.title}</p>
                    <p className={p.cardDesc}>{card.desc}</p>
                  </div>
                </div>

                <button
                  className={p.cardBtn}
                  onClick={() => setOpenModal(card.key)}
                >
                  {card.btn}
                </button>

              </div>
            </div>
          ))}
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