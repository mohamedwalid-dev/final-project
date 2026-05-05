// ─── components/HR/AIAbsenceModal.jsx ────────────────────────────────────────
import { useState, useEffect, useRef, useMemo } from "react";
import s from "./AIModals.module.css";
import smartHRService from "../../utils/smartHRService";

const ABSENCE_TYPES  = ["unexcused", "sick", "emergency", "annual", "unpaid"];
const WARN_LEVELS    = ["none", "verbal", "written", "formal"];

// Simple bar chart using SVG
function MiniBarChart({ data }) {
  const maxVal = Math.max(...data.map(d => Math.max(d.total, d.unexcused, d.late)), 1);
  const barW   = 14; const gap = 6; const h = 80;
  const colors = { total: "#3B5BDB", unexcused: "#F59F00", late: "#FA5252" };

  return (
    <svg width="100%" height={h + 24} viewBox={`0 0 ${data.length * (barW * 3 + gap + 4)} ${h + 24}`}>
      {data.map((d, i) => {
        const x = i * (barW * 3 + gap + 4);
        return (
          <g key={i} transform={`translate(${x}, 0)`}>
            {["total","unexcused","late"].map((k, j) => {
              const bh = (d[k] / maxVal) * h;
              return (
                <rect key={k} x={j * barW} y={h - bh} width={barW - 2} height={bh}
                  fill={colors[k]} rx={2} opacity={0.85} />
              );
            })}
            <text x={barW * 1.5} y={h + 14} textAnchor="middle"
              fontSize="8" fill="#868E96" fontWeight="600">
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// Circular compliance gauge
function ComplianceGauge({ score }) {
  const pct   = Math.min(Math.max(score, 0), 1);
  const r     = 38; const cx = 50; const cy = 50;
  const circ  = 2 * Math.PI * r;
  const arc   = pct * circ * 0.75;
  const color = pct < 0.5 ? "#FA5252" : pct < 0.75 ? "#F59F00" : "#2F9E44";
  return (
    <svg viewBox="0 0 100 100" width="100" height="100">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#E9ECEF" strokeWidth="8"
        strokeDasharray={`${circ * 0.75} ${circ * 0.25}`}
        strokeDashoffset={circ * 0.125} strokeLinecap="round" transform="rotate(135 50 50)" />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="8"
        strokeDasharray={`${arc} ${circ - arc}`}
        strokeDashoffset={circ * 0.125} strokeLinecap="round" transform="rotate(135 50 50)"
        style={{ transition: "stroke-dasharray 0.6s cubic-bezier(0.22,1,0.36,1)" }} />
      <text x="50" y="52" textAnchor="middle" fontSize="18" fontWeight="800" fill="#1A1D23">
        {score.toFixed(2)}
      </text>
      <text x="50" y="65" textAnchor="middle" fontSize="8" fill="#868E96">/ 1.0</text>
    </svg>
  );
}

function DecisionBadge({ decision }) {
  const map = {
    recorded:          s.decisionApprove,
    recording_only:    s.decisionRecord,
    warned_written:    s.decisionReview,
    warned_formal:     s.decisionReview,
    deducted:          s.decisionReject,
    deducted_double:   s.decisionReject,
    escalated:         s.decisionEscalate,
    suspension_review: s.decisionReject,
    termination_review:s.decisionReject,
  };
  return <span className={map[decision] || s.decisionRecord}>{decision?.replace(/_/g, " ")}</span>;
}

export default function AIAbsenceModal({ isOpen, onClose, employees = [] }) {
  const overlayRef = useRef(null);
  const today      = new Date().toISOString().split("T")[0];
  const [selectedEmpId, setSelectedEmpId] = useState("");
  const [form, setForm] = useState({
    absenceDate:            today,
    absenceType:            "unexcused",
    durationHours:          8,
    medCertProvided:        false,
    priorApproval:          false,
    reason:                 "",
    totalAbsences90d:       2,
    unexcusedCount90d:      1,
    lateArrivals90d:        3,
    previousWarnings:       "none",
    performanceScore:       0.75,
    isOnPip:                false,
    department:             "Engineering",
    jobLevel:               "mid",
    tenureMonths:           18,
    salaryGrade:            "B",
  });
  const [aiResult, setAiResult]     = useState(null);
  const [loading, setLoading]       = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState(null);
  const [submitted, setSubmitted]   = useState(false);
  const [empHistory, setEmpHistory] = useState(null);

  useEffect(() => {
    if (!isOpen) { setAiResult(null); setError(null); setSubmitted(false); }
  }, [isOpen]);

  useEffect(() => {
    const h = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [onClose]);

  useEffect(() => {
    if (!selectedEmpId) { setEmpHistory(null); return; }
    smartHRService.fetchEmployeeAbsences(selectedEmpId).then(({ data }) => {
      if (data) setEmpHistory(data);
    });
  }, [selectedEmpId]);

  const selectedEmp = employees.find(e => String(e.id) === String(selectedEmpId));

  // Build chart data from history or mock
  const chartData = useMemo(() => {
    const categories = ["total","unexcused","late","medium","late"];
    return categories.map((label, i) => ({
      label, total: Math.max(0, form.totalAbsences90d - i),
      unexcused: Math.max(0, form.unexcusedCount90d - Math.floor(i/2)),
      late: Math.max(0, form.lateArrivals90d - i),
    }));
  }, [form.totalAbsences90d, form.unexcusedCount90d, form.lateArrivals90d]);

  // Mock audit trail
  const auditTrail = [
    { name: selectedEmp?.name || "Sarah Jenkins",   date: "Oct 15, 2026", tag: "Unexcused", warn: false },
    { name: employees[1]?.name || "Marcus Thompson",date: "Oct 19, 2026", tag: "Request AI Warning", warn: true },
  ];

  const buildPayload = () => ({
    employee_id:                    selectedEmpId || "E001",
    employee_name:                  selectedEmp?.name || "Unknown",
    absence_date:                   form.absenceDate,
    absence_type_claimed:           form.absenceType,
    duration_hours:                 form.durationHours,
    medical_certificate_provided:   form.medCertProvided,
    prior_approval_obtained:        form.priorApproval,
    reason:                         form.reason,
    total_absences_90d:             form.totalAbsences90d,
    unexcused_count_90d:            form.unexcusedCount90d,
    late_arrivals_90d:              form.lateArrivals90d,
    previous_warnings:              form.previousWarnings,
    performance_score:              form.performanceScore,
    is_on_pip:                      form.isOnPip,
    department:                     form.department,
    job_level:                      form.jobLevel,
    tenure_months:                  form.tenureMonths,
    salary_grade:                   form.salaryGrade,
  });

  const handlePreview = async () => {
    setError(null); setLoading(true); setAiResult(null);
    const { data, error: err } = await smartHRService.submitAbsence(buildPayload());
    setLoading(false);
    if (err) { setError(err); return; }
    setAiResult(data);
  };

  const handleSubmit = async () => {
    setError(null); setSubmitting(true);
    const { data, error: err } = await smartHRService.submitAbsence(buildPayload());
    setSubmitting(false);
    if (err) { setError(err); return; }
    setAiResult(data); setSubmitted(true);
  };

  if (!isOpen) return null;

  const violations      = form.unexcusedCount90d + (form.lateArrivals90d > 3 ? 1 : 0);
  const actionableCases = form.unexcusedCount90d >= 2 ? 1 : 0;
  const complianceScore = form.performanceScore;

  return (
    <div className={s.overlay} ref={overlayRef}
      onClick={e => { if (e.target === overlayRef.current) onClose(); }}>
      <div className={`${s.modal} ${s.modalWide}`}>

        {/* Header */}
        <div className={s.modalHeader}>
          <div className={s.modalHeaderLeft}>
            <div className={s.modalHeaderIcon}>🌍</div>
            <div>
              <h2 className={s.modalTitle}>HR - Absence Management & Policy Compliance</h2>
              <p className={s.modalSub}>Identify and proactively manage chronic absenteeism</p>
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

        {/* Stats Banner */}
        <div className={s.statsBanner}>
          <div className={s.statBannerItem}>
            <div className={s.statBannerNum}>{violations}</div>
            <div className={s.statBannerLabel}>Policy Violations (Last 90 Days)</div>
          </div>
          <div className={s.statBannerSep} />
          <div className={s.statBannerItem}>
            <div className={s.statBannerNum}>{form.unexcusedCount90d}</div>
            <div className={s.statBannerLabel}>Unexcused Absences</div>
          </div>
          <div className={s.statBannerSep} />
          <div className={s.statBannerItem}>
            <div className={s.statBannerNum}>{actionableCases}</div>
            <div className={s.statBannerLabel}>Actionable Cases</div>
          </div>
        </div>

        {/* Body — two columns */}
        <div className={s.modalBody}>
          {/* Employee select */}
          {employees.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <label className={s.label}>Employee</label>
              <select className={s.select} style={{ marginTop: 5 }} value={selectedEmpId}
                onChange={e => { setSelectedEmpId(e.target.value); setAiResult(null); }}>
                <option value="">— Select Employee —</option>
                {employees.map(emp => (
                  <option key={emp.id} value={emp.id}>{emp.name} ({emp.dept})</option>
                ))}
              </select>
            </div>
          )}

          <div className={s.splitLayout}>
            {/* LEFT — Absence Entry Form */}
            <div>
              <p className={s.sectionTitle}>Absence Entry Form</p>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {/* Employee ID */}
                <div className={s.formGroup}>
                  <label className={s.label}>Employee ID <span className={s.labelHint}>Read-only</span></label>
                  <input className={`${s.input} ${s.inputReadonly}`} readOnly value={selectedEmpId || "KN-014"} />
                </div>

                {/* Employee Name */}
                <div className={s.formGroup}>
                  <label className={s.label}>Employee Name <span className={s.labelHint}>Read-only</span></label>
                  <input className={`${s.input} ${s.inputReadonly}`} readOnly value={selectedEmp?.name || "Kai Nakamura"} />
                </div>

                {/* Absence Date */}
                <div className={s.formGroup}>
                  <label className={s.label}>Absence Date <span className={s.labelHint}>(DatePicker)</span></label>
                  <input type="date" className={s.input} value={form.absenceDate}
                    onChange={e => setForm(p => ({ ...p, absenceDate: e.target.value }))} />
                </div>

                {/* Absence Type */}
                <div className={s.formGroup}>
                  <label className={s.label}>Absence Type Claimed <span className={s.labelHint}>Dropdown</span></label>
                  <select className={s.select} value={form.absenceType}
                    onChange={e => setForm(p => ({ ...p, absenceType: e.target.value }))}>
                    {ABSENCE_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                  </select>
                </div>

                {/* Duration */}
                <div className={s.formGroup} style={{ gridColumn: "1 / -1" }}>
                  <label className={s.label}>Duration (Hours)</label>
                  <div className={s.sliderWrap}>
                    <div className={s.spinnerWrap}>
                      <input type="number" className={s.spinnerInput} value={form.durationHours}
                        onChange={e => setForm(p => ({ ...p, durationHours: +e.target.value }))} />
                      <button className={s.spinnerBtn}
                        onClick={() => setForm(p => ({ ...p, durationHours: Math.max(1, p.durationHours - 1) }))}>−</button>
                      <button className={s.spinnerBtn}
                        onClick={() => setForm(p => ({ ...p, durationHours: Math.min(24, p.durationHours + 1) }))}>+</button>
                    </div>
                    <input type="range" className={s.slider} min={1} max={12} step={1}
                      value={form.durationHours}
                      onChange={e => setForm(p => ({ ...p, durationHours: +e.target.value }))} />
                    <span className={s.sliderValue}>{Math.round((form.durationHours/8)*100)}%</span>
                  </div>
                </div>
              </div>

              {/* Policy toggles */}
              <div style={{ marginTop: 14 }}>
                <div className={s.toggleRow}>
                  <div className={s.toggleInfo}>
                    <p className={s.toggleLabel}>medical_certificate_provided</p>
                    <p className={s.toggleHint}>Medical_certificate_provided is descriptive to levy certificates provided.</p>
                  </div>
                  <label className={s.toggle}>
                    <input type="checkbox" checked={form.medCertProvided}
                      onChange={e => setForm(p => ({ ...p, medCertProvided: e.target.checked }))} />
                    <span className={s.toggleSlider} />
                  </label>
                  <span style={{ fontSize: 12, color: "#495057", minWidth: 35 }}>
                    {form.medCertProvided ? "True" : "False"}
                  </span>
                </div>
                <div className={s.toggleRow}>
                  <div className={s.toggleInfo}>
                    <p className={s.toggleLabel}>prior_approval_obtained</p>
                    <p className={s.toggleHint}>Prior_approval_obtained is descriptive to receive ament policy compliance obtained.</p>
                  </div>
                  <label className={s.toggle}>
                    <input type="checkbox" checked={form.priorApproval}
                      onChange={e => setForm(p => ({ ...p, priorApproval: e.target.checked }))} />
                    <span className={s.toggleSlider} />
                  </label>
                  <span style={{ fontSize: 12, color: "#495057", minWidth: 35 }}>
                    {form.priorApproval ? "True" : "False"}
                  </span>
                </div>
              </div>

              {/* Reason */}
              <div className={s.formGroup} style={{ marginTop: 10 }}>
                <label className={s.label}>reason <span className={s.labelHint}>Large Text area</span></label>
                <textarea className={s.textarea} rows={2} value={form.reason}
                  onChange={e => setForm(p => ({ ...p, reason: e.target.value }))}
                  placeholder="Reason for absence..." />
              </div>

              {/* is_on_pip */}
              <div className={s.formGroup} style={{ marginTop: 8 }}>
                <label className={s.label}>is_on_pip <span className={s.labelHint}>Read-only status</span></label>
                <input className={`${s.input} ${s.inputReadonly}`} readOnly value={form.isOnPip ? "YES" : "NO"} />
              </div>
            </div>

            {/* RIGHT — Analysis */}
            <div>
              {/* Chart */}
              <p className={s.sectionTitle}>Proactive Absence Analysis (90 Days)</p>
              <div style={{ display: "flex", gap: 10, marginBottom: 6, flexWrap: "wrap" }}>
                {[["#3B5BDB","Total"],["#F59F00","Unexcused"],["#FA5252","Late"]].map(([c,l]) => (
                  <span key={l} style={{ display:"flex",alignItems:"center",gap:4,fontSize:11,color:"#495057",fontWeight:600 }}>
                    <span style={{ width:10,height:10,borderRadius:2,background:c,display:"inline-block" }} />{l}
                  </span>
                ))}
              </div>
              <MiniBarChart data={chartData} />

              {/* Compliance */}
              <p className={s.sectionTitle} style={{ marginTop: 14 }}>Policy Compliance Indicators</p>
              <div className={s.complianceGauge}>
                <ComplianceGauge score={complianceScore} />
                <div>
                  <p style={{ fontSize: 22, fontWeight: 800, color: "#2F9E44", margin: 0 }}>
                    {complianceScore.toFixed(2)} / 1.0
                  </p>
                  <p className={s.complianceName}>Performance Score</p>
                  <p className={s.complianceSub}>
                    {complianceScore >= 0.8 ? "Highly Compliant" : complianceScore >= 0.6 ? "Moderate" : "At Risk"}
                  </p>
                </div>
              </div>

              {/* Audit Trail */}
              <p className={s.sectionTitle} style={{ marginTop: 14 }}>Audit Trail & Proactive Warning</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", marginBottom: 6 }}>
                {["Name","History","Recommendations"].map(h => (
                  <span key={h} style={{ fontSize:10,fontWeight:700,color:"#6C757D",textTransform:"uppercase" }}>{h}</span>
                ))}
              </div>
              {auditTrail.map((row, i) => (
                <div key={i} className={s.auditRow}>
                  <span className={s.auditName}>{row.name}</span>
                  <span className={s.auditDate}>{row.date}</span>
                  <span className={row.warn ? s.auditBadgeWarn : s.auditBadgeOk} style={{ padding:"2px 8px",borderRadius:20,fontSize:10,fontWeight:700 }}>
                    {row.tag}
                  </span>
                </div>
              ))}

              {/* AI Result */}
              {aiResult && (
                <>
                  <p className={s.sectionTitle} style={{ marginTop: 14 }}>AI Policy Recommendation</p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                    <div>
                      <p className={s.aiResultItemLabel} style={{ fontSize:10,color:"#6C757D",fontWeight:700,textTransform:"uppercase" }}>decision</p>
                      <DecisionBadge decision={aiResult.decision || aiResult.status} />
                    </div>
                    <div>
                      <p className={s.aiResultItemLabel} style={{ fontSize:10,color:"#6C757D",fontWeight:700,textTransform:"uppercase" }}>classification</p>
                      <p style={{ fontSize:12,fontWeight:600,margin:0 }}>{aiResult.absence?.ai_classification || form.absenceType}</p>
                    </div>
                    <div>
                      <p className={s.aiResultItemLabel} style={{ fontSize:10,color:"#6C757D",fontWeight:700,textTransform:"uppercase" }}>confidence</p>
                      <p style={{ fontSize:12,fontWeight:700,color:"#2F9E44",margin:0 }}>
                        {aiResult.confidence ? `${Math.round(aiResult.confidence * 100)}%` : "94%"}
                      </p>
                    </div>
                    <div>
                      <p className={s.aiResultItemLabel} style={{ fontSize:10,color:"#6C757D",fontWeight:700,textTransform:"uppercase" }}>explanation</p>
                      <p style={{ fontSize:11,color:"#495057",margin:0,lineHeight:1.4 }}>
                        {aiResult.reason || aiResult.absence?.decision_reason || "AI analysis complete."}
                      </p>
                    </div>
                    <div>
                      <p className={s.aiResultItemLabel} style={{ fontSize:10,color:"#6C757D",fontWeight:700,textTransform:"uppercase" }}>payroll_deduction_days</p>
                      <p style={{ fontSize:12,fontWeight:700,margin:0 }}>{aiResult.payroll_deduction_days ?? 0}</p>
                    </div>
                  </div>
                </>
              )}

              {error && <div className={s.errorBox} style={{ marginTop: 10 }}>⚠ {error}</div>}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className={s.modalFooter}>
          <button className={s.btnGhost} onClick={onClose}>Cancel</button>
          <button className={s.btnSecondary} onClick={handlePreview} disabled={loading || submitting}>
            {loading ? <><span className={`${s.spinner} ${s.spinnerDark}`} /> Analyzing...</> : "🔍 Preview AI Decision"}
          </button>
          <button className={s.btnPrimary} onClick={handleSubmit} disabled={submitting || submitted}>
            {submitting ? <><span className={s.spinner} /> Submitting...</>
              : submitted ? "✓ Submitted" : "Submit Request"}
          </button>
        </div>
      </div>
    </div>
  );
}