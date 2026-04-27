// ─── components/HR/AISalaryModal.jsx ─────────────────────────────────────────
import { useState, useEffect, useRef } from "react";
import s from "./AIModals.module.css";
import smartHRService from "../../utils/smartHRService";

function DecisionBadge({ decision }) {
  const map = {
    approve_increment:     s.decisionApprove,
    approved:              s.decisionApprove,
    escalate_to_director:  s.decisionEscalate,
    escalated:             s.decisionEscalate,
    defer:                 s.decisionReview,
    deferred:              s.decisionReview,
    reject:                s.decisionReject,
    rejected:              s.decisionReject,
  };
  const label = decision?.replace(/_/g, " ");
  return <span className={map[decision] || s.decisionRecord}>{label}</span>;
}

const JOB_LEVELS  = ["junior", "mid", "senior", "lead", "principal", "manager", "director"];
const SALARY_GRADES = ["A", "B", "C", "D", "E"];

export default function AISalaryModal({ isOpen, onClose, employees = [] }) {
  const overlayRef = useRef(null);
  const [selectedEmpId, setSelectedEmpId] = useState("");
  const [form, setForm] = useState({
    currentSalary:      50000,
    incrementPct:       0.10,
    marketMedian:       60000,
    marketGapPct:       0.15,
    monthsSinceLast:    12,
    monthsInRole:       18,
    kpiAchievement:     0.90,
    budgetUtilization:  0.80,
    availablePool:      200000,
    isOnPip:            false,
    isOnProbation:      false,
    performanceScore:   0.85,
    department:         "Engineering",
    jobLevel:           "mid",
    salaryGrade:        "B",
  });
  const [aiResult, setAiResult]   = useState(null);
  const [loading, setLoading]     = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]         = useState(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!isOpen) { setAiResult(null); setError(null); setSubmitted(false); }
  }, [isOpen]);

  useEffect(() => {
    const h = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [onClose]);

  const selectedEmp = employees.find(e => String(e.id) === String(selectedEmpId));

  const buildPayload = () => ({
    employee_id:                  selectedEmpId || "E001",
    employee_name:                selectedEmp?.name || "Unknown",
    current_salary_egp:           form.currentSalary,
    requested_increment_pct:      form.incrementPct,
    market_median_egp:            form.marketMedian,
    market_gap_pct:               form.marketGapPct,
    months_since_last_increment:  form.monthsSinceLast,
    months_in_role:               form.monthsInRole,
    kpi_achievement:              form.kpiAchievement,
    budget_utilization:           form.budgetUtilization,
    available_pool_egp:           form.availablePool,
    is_on_pip:                    form.isOnPip,
    is_on_probation:              form.isOnProbation,
    performance_score:            form.performanceScore,
    department:                   form.department,
    job_level:                    form.jobLevel,
    salary_grade:                 form.salaryGrade,
    appraisal_cycle:              "Annual",
  });

  const handlePreview = async () => {
    setError(null); setLoading(true); setAiResult(null);
    const { data, error: err } = await smartHRService.submitSalaryReview(buildPayload());
    setLoading(false);
    if (err) { setError(err); return; }
    setAiResult(data);
  };

  const handleSubmit = async () => {
    setError(null); setSubmitting(true);
    const { data, error: err } = await smartHRService.submitSalaryReview(buildPayload());
    setSubmitting(false);
    if (err) { setError(err); return; }
    setAiResult(data); setSubmitted(true);
  };

  if (!isOpen) return null;

  const projectedSalary = Math.round(form.currentSalary * (1 + form.incrementPct));

  return (
    <div className={s.overlay} ref={overlayRef}
      onClick={e => { if (e.target === overlayRef.current) onClose(); }}>
      <div className={s.modal}>

        {/* Header */}
        <div className={s.modalHeader}>
          <div className={s.modalHeaderLeft}>
            <div className={s.modalHeaderIcon}>💰</div>
            <div>
              <h2 className={s.modalTitle}>HR - Salary Review Proposal</h2>
              <p className={s.modalSub}>Market-indexed, performance-based compensation analysis</p>
            </div>
          </div>
          <div className={s.modalHeaderRight}>
            <div className={s.userTag}>
              <div className={s.userAvatar}>AS</div>
              <span className={s.userName}>Alex Sterling</span>
            </div>
            <button className={s.closeBtn} onClick={onClose}>✕</button>
          </div>
        </div>

        {/* Employee Banner */}
        <div className={s.empBanner}>
          {employees.length > 0 ? (
            <select className={s.empSelect} value={selectedEmpId}
              onChange={e => { setSelectedEmpId(e.target.value); setAiResult(null); }}>
              <option value="">— Select Employee —</option>
              {employees.map(emp => (
                <option key={emp.id} value={emp.id}>
                  Proposal Data for {emp.name} ({emp.dept})
                </option>
              ))}
            </select>
          ) : (
            <span>Proposal Data for Kai Nakamura (KN-014)</span>
          )}
        </div>

        {/* Body */}
        <div className={s.modalBody}>
          <div className={s.formGrid}>
            {/* Employee ID */}
            <div className={s.formGroup}>
              <label className={s.label}>Employee ID</label>
              <input className={`${s.input} ${s.inputReadonly}`} readOnly
                value={selectedEmpId || "E123"} />
            </div>

            {/* Department */}
            <div className={s.formGroup}>
              <label className={s.label}>Department</label>
              <select className={s.select} value={form.department}
                onChange={e => setForm(p => ({ ...p, department: e.target.value }))}>
                {["Engineering","Design","Marketing","Finance","HR","Sales","Support","Product"]
                  .map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

            {/* Current Salary */}
            <div className={s.formGroup}>
              <label className={s.label}>Current Salary (EGP)</label>
              <input type="number" className={s.input} value={form.currentSalary}
                onChange={e => setForm(p => ({ ...p, currentSalary: +e.target.value }))} />
            </div>

            {/* Increment % */}
            <div className={s.formGroup}>
              <label className={s.label}>Increment Request</label>
              <div className={s.sliderWrap}>
                <input type="range" className={s.slider} min={0.01} max={0.50} step={0.01}
                  value={form.incrementPct}
                  onChange={e => setForm(p => ({ ...p, incrementPct: +e.target.value }))} />
                <span className={s.sliderValue}>{Math.round(form.incrementPct * 100)}%</span>
              </div>
            </div>

            {/* KPI Achievement */}
            <div className={s.formGroup}>
              <label className={s.label}>KPI Achievement</label>
              <div className={s.sliderWrap}>
                <input type="range" className={s.slider} min={0} max={1} step={0.01}
                  value={form.kpiAchievement}
                  onChange={e => setForm(p => ({ ...p, kpiAchievement: +e.target.value }))} />
                <span className={s.sliderValue}>{Math.round(form.kpiAchievement * 100)}%</span>
              </div>
            </div>

            {/* Performance Score */}
            <div className={s.formGroup}>
              <label className={s.label}>Performance Score</label>
              <div className={s.sliderWrap}>
                <input type="range" className={s.slider} min={0} max={1} step={0.01}
                  value={form.performanceScore}
                  onChange={e => setForm(p => ({ ...p, performanceScore: +e.target.value }))} />
                <span className={s.sliderValue}>{form.performanceScore.toFixed(2)}</span>
              </div>
            </div>

            {/* Job Level */}
            <div className={s.formGroup}>
              <label className={s.label}>Job Level</label>
              <select className={s.select} value={form.jobLevel}
                onChange={e => setForm(p => ({ ...p, jobLevel: e.target.value }))}>
                {JOB_LEVELS.map(l => <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>)}
              </select>
            </div>

            {/* Salary Grade */}
            <div className={s.formGroup}>
              <label className={s.label}>Salary Grade</label>
              <select className={s.select} value={form.salaryGrade}
                onChange={e => setForm(p => ({ ...p, salaryGrade: e.target.value }))}>
                {SALARY_GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
              </select>
            </div>

            {/* Market Median */}
            <div className={s.formGroup}>
              <label className={s.label}>Market Median (EGP)</label>
              <input type="number" className={s.input} value={form.marketMedian}
                onChange={e => setForm(p => ({ ...p, marketMedian: +e.target.value }))} />
            </div>

            {/* Available Pool */}
            <div className={s.formGroup}>
              <label className={s.label}>Available Pool (EGP)</label>
              <input type="number" className={s.input} value={form.availablePool}
                onChange={e => setForm(p => ({ ...p, availablePool: +e.target.value }))} />
            </div>

            {/* Months since last */}
            <div className={s.formGroup}>
              <label className={s.label}>Months Since Last Raise</label>
              <input type="number" className={s.input} value={form.monthsSinceLast} min={0}
                onChange={e => setForm(p => ({ ...p, monthsSinceLast: +e.target.value }))} />
            </div>

            {/* Projected salary preview */}
            <div className={s.formGroup}>
              <label className={s.label}>Projected Salary</label>
              <input className={`${s.input} ${s.inputReadonly}`} readOnly
                value={`EGP ${projectedSalary.toLocaleString()}`} />
            </div>
          </div>

          {/* Error */}
          {error && <div className={s.errorBox}>⚠ {error}</div>}

          {/* AI Result */}
          {aiResult && (
            <div className={s.aiResultPanel}>
              <p className={s.aiResultTitle}><span>💡</span> AI Salary Decision</p>
              <div className={s.aiResultGrid}>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>Decision</p>
                  <DecisionBadge decision={aiResult.decision || aiResult.status} />
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>Confidence</p>
                  <span className={s.confBadge}>
                    {aiResult.confidence
                      ? `${Math.round(aiResult.confidence * 100)}%`
                      : aiResult.review?.confidence_score
                        ? `${Math.round(aiResult.review.confidence_score * 100)}%`
                        : "—"}
                  </span>
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>Review ID</p>
                  <p className={s.aiResultItemValue}>#{aiResult.review_id || "—"}</p>
                </div>
              </div>
              {(aiResult.reason || aiResult.review?.decision_reason) && (
                <p className={s.aiResultReason}>
                  📝 {aiResult.reason || aiResult.review?.decision_reason}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={s.modalFooter}>
          <button className={s.btnGhost} onClick={onClose}>Cancel</button>
          <button className={s.btnSecondary} onClick={handlePreview} disabled={loading || submitting}>
            {loading ? <><span className={`${s.spinner} ${s.spinnerDark}`} /> Analyzing...</> : "🔍 Preview AI Analysis"}
          </button>
          <button className={s.btnPrimary} onClick={handleSubmit} disabled={submitting || submitted}>
            {submitting ? <><span className={s.spinner} /> Submitting...</>
              : submitted ? "✓ Submitted" : "Submit Proposal"}
          </button>
        </div>
      </div>
    </div>
  );
}