// ─── components/HR/AIIncentivesModal.jsx ─────────────────────────────────────
import { useState, useEffect, useRef } from "react";
import s from "./AIModals.module.css";
import smartHRService from "../../utils/smartHRService";
import { AlertTriangle, Bot, CheckCircle2, Search, Trophy, X } from "lucide-react";

const INCENTIVE_TYPES = [
  { value: "performance_bonus",    label: "Performance Bonus" },
  { value: "overtime_compensation",label: "Overtime Compensation" },
  { value: "retention_bonus",      label: "Retention Bonus" },
  { value: "project_bonus",        label: "Project Bonus" },
  { value: "annual_bonus",         label: "Annual Bonus" },
];
const JOB_LEVELS  = ["junior", "mid", "senior", "lead", "principal", "manager", "director"];
const SALARY_GRADES = ["A", "B", "C", "D", "E"];

function DecisionBadge({ decision }) {
  const map = {
    approved:          s.decisionApprove,
    partial:           s.decisionReview,
    rejected:          s.decisionReject,
    escalated:         s.decisionEscalate,
    escalated_ceo:     s.decisionEscalate,
    manual_review:     s.decisionReview,
  };
  return <span className={map[decision] || s.decisionRecord}>{decision?.replace(/_/g, " ")}</span>;
}

export default function AIIncentivesModal({ isOpen, onClose, employees = [] }) {
  const overlayRef = useRef(null);
  const [selectedEmpId, setSelectedEmpId] = useState("");
  const [form, setForm] = useState({
    incentiveType:           "performance_bonus",
    requestedAmount:         10000,
    kpiAchievement:          0.90,
    performanceScore:        0.85,
    monthlySalary:           15000,
    tenureMonths:            24,
    isOnPip:                 false,
    isCriticalTalent:        false,
    budgetRemaining:         150000,
    perfTrend:               "stable",
    reason:                  "",
    department:              "Engineering",
    jobLevel:                "mid",
    salaryGrade:             "B",
  });
  const [aiResult, setAiResult]     = useState(null);
  const [loading, setLoading]       = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState(null);
  const [submitted, setSubmitted]   = useState(false);

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
    employee_id:                      selectedEmpId || "E001",
    employee_name:                    selectedEmp?.name || "Unknown",
    incentive_type:                   form.incentiveType,
    requested_amount_egp:             form.requestedAmount,
    kpi_achievement:                  form.kpiAchievement,
    performance_score:                form.performanceScore,
    monthly_salary_egp:               form.monthlySalary,
    tenure_months:                    form.tenureMonths,
    is_on_pip:                        form.isOnPip,
    is_critical_talent:               form.isCriticalTalent,
    incentive_budget_remaining_egp:   form.budgetRemaining,
    perf_trend:                       form.perfTrend,
    reason:                           form.reason,
    department:                       form.department,
    job_level:                        form.jobLevel,
    salary_grade:                     form.salaryGrade,
  });

  const handlePreview = async () => {
    setError(null); setLoading(true); setAiResult(null);
    const { data, error: err } = await smartHRService.submitIncentive(buildPayload());
    setLoading(false);
    if (err) { setError(err); return; }
    setAiResult(data);
  };

  const handleSubmit = async () => {
    setError(null); setSubmitting(true);
    const { data, error: err } = await smartHRService.submitIncentive(buildPayload());
    setSubmitting(false);
    if (err) { setError(err); return; }
    setAiResult(data); setSubmitted(true);
  };

  if (!isOpen) return null;

  return (
    <div className={s.overlay} ref={overlayRef}
      onClick={e => { if (e.target === overlayRef.current) onClose(); }}>
      <div className={s.modal}>

        {/* Header */}
        <div className={s.modalHeader}>
          <div className={s.modalHeaderLeft}>
            <div className={s.modalHeaderIcon}>
              <Trophy className={s.modalIconSvg} aria-hidden="true" />
            </div>
            <div>
              <h2 className={s.modalTitle}>HR - Incentives Proposal</h2>
              <p className={s.modalSub}>Data-driven, motivating reward programs</p>
            </div>
          </div>
          <div className={s.modalHeaderRight}>
            <div className={s.userTag}>
              <div className={s.userAvatar}>AS</div>
              <span className={s.userName}>Alex Sterling</span>
            </div>
            <button className={s.closeBtn} onClick={onClose} aria-label="Close">
              <X className={s.inlineIcon} aria-hidden="true" />
            </button>
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

            {/* Employee Name */}
            <div className={s.formGroup}>
              <label className={s.label}>Employee Name</label>
              <input className={`${s.input} ${s.inputReadonly}`} readOnly
                value={selectedEmp?.name || "—"} />
            </div>

            {/* Requested Amount */}
            <div className={s.formGroup}>
              <label className={s.label}>requested_amount_egp <span className={s.labelHint}>EGP</span></label>
              <div className={s.spinnerWrap}>
                <input type="number" className={s.spinnerInput} value={form.requestedAmount}
                  onChange={e => setForm(p => ({ ...p, requestedAmount: +e.target.value }))} />
                <button className={s.spinnerBtn}
                  onClick={() => setForm(p => ({ ...p, requestedAmount: Math.max(0, p.requestedAmount - 1000) }))}>−</button>
                <button className={s.spinnerBtn}
                  onClick={() => setForm(p => ({ ...p, requestedAmount: p.requestedAmount + 1000 }))}>+</button>
              </div>
            </div>

            {/* Incentive Type */}
            <div className={s.formGroup}>
              <label className={s.label}>Incentive Type</label>
              <select className={s.select} value={form.incentiveType}
                onChange={e => setForm(p => ({ ...p, incentiveType: e.target.value }))}>
                {INCENTIVE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>

            {/* Reason */}
            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.label}>reason <span className={s.labelHint}>Large Text area</span></label>
              <textarea className={s.textarea} rows={3} value={form.reason}
                onChange={e => setForm(p => ({ ...p, reason: e.target.value }))}
                placeholder="Reason for incentive request..." />
            </div>

            {/* Department */}
            <div className={s.formGroup}>
              <label className={s.label}>department</label>
              <select className={s.select} value={form.department}
                onChange={e => setForm(p => ({ ...p, department: e.target.value }))}>
                {["Engineering","Design","Marketing","Finance","HR","Sales","Support","Product"]
                  .map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

            {/* Job Level */}
            <div className={s.formGroup}>
              <label className={s.label}>job_level</label>
              <select className={s.select} value={form.jobLevel}
                onChange={e => setForm(p => ({ ...p, jobLevel: e.target.value }))}>
                {JOB_LEVELS.map((l, i) => <option key={l} value={l}>Level {i + 1}</option>)}
              </select>
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

            {/* Salary Grade */}
            <div className={s.formGroup}>
              <label className={s.label}>salary_grade</label>
              <select className={s.select} value={form.salaryGrade}
                onChange={e => setForm(p => ({ ...p, salaryGrade: e.target.value }))}>
                {SALARY_GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
              </select>
            </div>

            {/* Budget Remaining */}
            <div className={s.formGroup}>
              <label className={s.label}>Budget Remaining (EGP)</label>
              <input type="number" className={s.input} value={form.budgetRemaining}
                onChange={e => setForm(p => ({ ...p, budgetRemaining: +e.target.value }))} />
            </div>
          </div>

          {/* Error */}
          {error && <div className={s.errorBox}><AlertTriangle className={s.inlineIcon} aria-hidden="true" /> {error}</div>}

          {/* AI Result */}
          {aiResult && (
            <div className={s.aiResultPanel}>
              <p className={s.aiResultTitle}><Bot className={s.inlineIcon} aria-hidden="true" /> AI Incentive Decision</p>
              <div className={s.aiResultGrid}>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>Decision</p>
                  <DecisionBadge decision={aiResult.decision || aiResult.status} />
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>Approved Amount</p>
                  <p className={s.aiResultItemValue} style={{ color: "#2F9E44" }}>
                    {aiResult.approved_amount
                      ? `EGP ${Number(aiResult.approved_amount).toLocaleString()}`
                      : "—"}
                  </p>
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>Incentive ID</p>
                  <p className={s.aiResultItemValue}>#{aiResult.incentive_id || "—"}</p>
                </div>
              </div>
              {(aiResult.reason || aiResult.incentive?.decision_reason) && (
                <p className={s.aiResultReason}>
                  {aiResult.reason || aiResult.incentive?.decision_reason}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={s.modalFooter}>
          <button className={s.btnGhost} onClick={onClose}>Cancel</button>
          <button className={s.btnSecondary} onClick={handlePreview} disabled={loading || submitting}>
            {loading ? <><span className={`${s.spinner} ${s.spinnerDark}`} /> Analyzing...</> : <><Search className={s.inlineIcon} aria-hidden="true" /> Preview AI Decision</>}
          </button>
          <button className={s.btnPrimary} onClick={handleSubmit} disabled={submitting || submitted}>
            {submitting ? <><span className={s.spinner} /> Submitting...</>
              : submitted ? <><CheckCircle2 className={s.inlineIcon} aria-hidden="true" /> Submitted</> : "Submit Request"}
          </button>
        </div>
      </div>
    </div>
  );
}
