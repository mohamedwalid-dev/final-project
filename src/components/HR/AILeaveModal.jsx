// ─── components/HR/AILeaveModal.jsx ──────────────────────────────────────────
import { useState, useEffect, useRef } from "react";
import s from "./AIModals.module.css";
import smartHRService from "../../utils/smartHRService";

const LEAVE_TYPES = ["annual", "sick", "emergency", "unpaid"];
const WORKLOAD_OPTIONS = ["low", "medium", "high"];

function CircularGauge({ value, max = 5, size = 90 }) {
  const pct   = Math.min(value / max, 1);
  const r     = 36; const cx = 50; const cy = 50;
  const circ  = 2 * Math.PI * r;
  const dash  = pct * circ * 0.75;
  const color = pct < 0.4 ? "#FA5252" : pct < 0.7 ? "#F59F00" : "#2F9E44";
  return (
    <div className={s.gaugeWrap} style={{ width: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size} className={s.gaugeSvg}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#E9ECEF" strokeWidth="9"
          strokeDasharray={`${circ * 0.75} ${circ * 0.25}`}
          strokeDashoffset={circ * 0.125} strokeLinecap="round" transform="rotate(135 50 50)" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="9"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={circ * 0.125} strokeLinecap="round" transform="rotate(135 50 50)"
          style={{ transition: "stroke-dasharray 0.5s cubic-bezier(0.22,1,0.36,1)" }} />
        <text x="50" y="54" textAnchor="middle" fontSize="18" fontWeight="800" fill="#1A1D23">
          {value}
        </text>
        <text x="50" y="68" textAnchor="middle" fontSize="9" fill="#868E96">/ {max}</text>
      </svg>
    </div>
  );
}

function DecisionBadge({ decision }) {
  const map = {
    approved:       s.decisionApprove,
    approve:        s.decisionApprove,
    rejected:       s.decisionReject,
    reject:         s.decisionReject,
    escalated:      s.decisionEscalate,
    manual_review:  s.decisionReview,
    recording_only: s.decisionRecord,
    processing:     s.decisionRecord,
  };
  return <span className={map[decision] || s.decisionRecord}>{decision?.replace("_", " ")}</span>;
}

export default function AILeaveModal({ isOpen, onClose, employees = [] }) {
  const overlayRef = useRef(null);
  const [selectedEmpId, setSelectedEmpId] = useState("");
  const [form, setForm] = useState({
    startDate: new Date().toISOString().split("T")[0],
    requestedDays: 1,
    leaveType: "annual",
    leaveBalance: 0,
    reason: "",
    teamWorkload: "medium",
    performanceScore: 3,
    attendanceRate: 90,
  });
  const [aiResult, setAiResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
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
    employee_id:       selectedEmpId || "E001",
    employee_name:     selectedEmp?.name || "Unknown",
    requested_days:    form.requestedDays,
    leave_type:        form.leaveType,
    leave_balance:     form.leaveBalance,
    reason:            form.reason,
    team_workload:     form.teamWorkload,
    performance_score: form.performanceScore / 5,
    attendance_rate:   form.attendanceRate / 100,
    start_date:        form.startDate,
  });

  const handlePreview = async () => {
    if (!selectedEmpId && employees.length > 0) { setError("Please select an employee."); return; }
    setError(null); setLoading(true); setAiResult(null);
    const { data, error: err } = await smartHRService.submitLeave(buildPayload());
    setLoading(false);
    if (err) { setError(err); return; }
    setAiResult(data);
  };

  const handleSubmit = async () => {
    if (!selectedEmpId && employees.length > 0) { setError("Please select an employee."); return; }
    setError(null); setSubmitting(true);
    const { data, error: err } = await smartHRService.submitLeave(buildPayload());
    setSubmitting(false);
    if (err) { setError(err); return; }
    setAiResult(data); setSubmitted(true);
  };

  if (!isOpen) return null;

  return (
    <div className={s.overlay} ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}>
      <div className={s.modal}>

        {/* Header */}
        <div className={s.modalHeader}>
          <div className={s.modalHeaderLeft}>
            <div className={s.modalHeaderIcon}>🌿</div>
            <div>
              <h2 className={s.modalTitle}>Request New AI Leave</h2>
              <p className={s.modalSub}>Smart Leaves — Predictive Scheduling</p>
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
                  {emp.name} ({emp.dept}) · Balance: {emp.leave_balance ?? form.leaveBalance}d
                </option>
              ))}
            </select>
          ) : (
            <>
              <div className={s.empBannerIcon} style={{ background: "#3B5BDB" }}>SJ</div>
              <span>Employee: Sarah Jenkins (SJ-014)</span>
              <span className={s.empBannerMeta}> / Avail. Balance: 21 Days (Annual)</span>
            </>
          )}
        </div>

        {/* Body */}
        <div className={s.modalBody}>
          <div className={s.formGrid}>
            {/* Start Date */}
            <div className={s.formGroup}>
              <label className={s.label}>Start Date <span className={s.labelHint}>(DatePicker)</span></label>
              <input type="date" className={s.input} value={form.startDate}
                onChange={e => setForm(p => ({ ...p, startDate: e.target.value }))} />
            </div>

            {/* Requested Days */}
            <div className={s.formGroup}>
              <label className={s.label}>Requested Days <span className={s.labelHint}>Number spinner</span></label>
              <div className={s.spinnerWrap}>
                <input type="number" className={s.spinnerInput} value={form.requestedDays}
                  onChange={e => setForm(p => ({ ...p, requestedDays: Math.max(1, +e.target.value) }))} min={1} />
                <button className={s.spinnerBtn}
                  onClick={() => setForm(p => ({ ...p, requestedDays: Math.max(1, p.requestedDays - 1) }))}>−</button>
                <button className={s.spinnerBtn}
                  onClick={() => setForm(p => ({ ...p, requestedDays: p.requestedDays + 1 }))}>+</button>
              </div>
            </div>

            {/* Leave Type */}
            <div className={s.formGroup}>
              <label className={s.label}>Leave Type <span className={s.labelHint}>(Dropdown)</span></label>
              <select className={s.select} value={form.leaveType}
                onChange={e => setForm(p => ({ ...p, leaveType: e.target.value }))}>
                {LEAVE_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
              </select>
            </div>

            {/* Leave Balance */}
            <div className={s.formGroup}>
              <label className={s.label}>Leave Balance</label>
              <input type="number" className={s.input} value={form.leaveBalance}
                onChange={e => setForm(p => ({ ...p, leaveBalance: +e.target.value }))} min={0} />
            </div>

            {/* Reason */}
            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.label}>Reason</label>
              <textarea className={s.textarea} value={form.reason} rows={2}
                onChange={e => setForm(p => ({ ...p, reason: e.target.value }))}
                placeholder="Reason for leave request..." />
            </div>

            {/* Team Workload */}
            <div className={s.formGroup}>
              <label className={s.label}>Team Workload</label>
              <select className={s.select} value={form.teamWorkload}
                onChange={e => setForm(p => ({ ...p, teamWorkload: e.target.value }))}>
                {WORKLOAD_OPTIONS.map(w => <option key={w} value={w}>{w.charAt(0).toUpperCase() + w.slice(1)}</option>)}
              </select>
            </div>

            {/* Performance Score Gauge */}
            <div className={s.formGroup} style={{ alignItems: "center" }}>
              <label className={s.label}>Performance Score <span className={s.labelHint}>(Circular Gauge)</span></label>
              <CircularGauge value={form.performanceScore} max={5} />
              <input type="range" className={s.slider} min={1} max={5} step={1}
                value={form.performanceScore}
                onChange={e => setForm(p => ({ ...p, performanceScore: +e.target.value }))}
                style={{ width: "100%", marginTop: 4 }} />
            </div>

            {/* Attendance Rate */}
            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.label}>Attendance Rate <span className={s.labelHint}>percentage</span></label>
              <div className={s.sliderWrap}>
                <input type="range" className={s.slider} min={0} max={100} step={1}
                  value={form.attendanceRate}
                  onChange={e => setForm(p => ({ ...p, attendanceRate: +e.target.value }))} />
                <span className={s.sliderValue}>{form.attendanceRate}%</span>
              </div>
            </div>
          </div>

          {/* Error */}
          {error && <div className={s.errorBox}>⚠ {error}</div>}

          {/* AI Result */}
          {aiResult && (
            <div className={s.aiResultPanel}>
              <p className={s.aiResultTitle}>
                <span>🤖</span>
                AI {submitted ? "Leave Policy Decision" : "Absence Policy Recommendation (Draft)"}
              </p>
              <div className={s.aiResultGrid}>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>decision</p>
                  <DecisionBadge decision={aiResult.decision || aiResult.status} />
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>classification</p>
                  <p className={s.aiResultItemValue} style={{ fontSize: 12 }}>
                    {aiResult.leave?.leave_type || form.leaveType}
                  </p>
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>confidence</p>
                  <span className={s.confBadge}>
                    {aiResult.leave?.confidence_score
                      ? `${Math.round(aiResult.leave.confidence_score * 100)}%`
                      : "94%"}
                  </span>
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>reason</p>
                  <p className={s.aiResultItemValue} style={{ fontSize: 12 }}>
                    {aiResult.message?.replace("✅ Decision ready: ", "") || "AI analysis complete"}
                  </p>
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>escalation_required</p>
                  <span className={aiResult.decision === "escalated" ? s.decisionEscalate : s.decisionApprove}>
                    {aiResult.decision === "escalated" ? "Required" : "Not required"}
                  </span>
                </div>
                <div className={s.aiResultItem}>
                  <p className={s.aiResultItemLabel}>leave_id</p>
                  <p className={s.aiResultItemValue}>#{aiResult.leave_id || "—"}</p>
                </div>
              </div>
            </div>
          )}
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