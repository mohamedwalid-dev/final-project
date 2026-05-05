import { useState, useEffect, useRef, useCallback, useReducer, useMemo } from "react";

// ─── Constants ────────────────────────────────────────────────────────────────
const STEPS = Object.freeze({
  EMAIL:   "email",
  OTP:     "otp",
  RESET:   "reset",
  SUCCESS: "success",
});

// 🟡 Fix #3: STEP_ORDER now used in navigation logic (progress indicator)
const STEP_ORDER = [STEPS.EMAIL, STEPS.OTP, STEPS.RESET];

// ─── Error Reducer ────────────────────────────────────────────────────────────
function errorReducer(state, action) {
  switch (action.type) {
    case "SET":       return { ...state, [action.field]: action.message };
    case "CLEAR_ALL": return {};
    case "CLEAR": {
      const next = { ...state };
      delete next[action.field];
      return next;
    }
    default: return state;
  }
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

/**
 * SECURITY BOUNDARY — UI manages countdown only.
 * Backend must handle: OTP validation, expiry TTL (5 min),
 * brute-force lockout, resend rate-limiting (max 3/hour).
 */
function useOtpTimer(initial = 60) {
  const [timer, setTimer]         = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const intervalRef               = useRef(null);

  const clear = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    clear();
    setTimer(initial);
    setIsRunning(true);
    intervalRef.current = setInterval(() => {
      setTimer(prev => {
        if (prev <= 1) { clear(); setIsRunning(false); return 0; }
        return prev - 1;
      });
    }, 1000);
  }, [initial, clear]);

  const reset = useCallback(() => {
    clear();
    setTimer(0);
    setIsRunning(false);
  }, [clear]);

  // 🟡 Fix #2: Explicit return in useEffect for better readability
  useEffect(() => {
    return () => clear();
  }, [clear]);

  return { timer, isRunning, start, reset };
}

function usePasswordStrength(password) {
  return useMemo(() => {
    if (!password) return { score: 0, label: "", color: "" };
    let score = 0;
    if (password.length >= 8)            score++;
    if (/[A-Z]/.test(password))          score++;
    if (/[0-9]/.test(password))          score++;
    if (/[^A-Za-z0-9]/.test(password))  score++;
    return {
      score,
      label: ["", "Weak", "Fair", "Good", "Strong"][score],
      color: ["", "#ef4444", "#f59e0b", "#3b82f6", "#10b981"][score],
    };
  }, [password]);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Logo() {
  return (
    <div className="fp-logo" role="img" aria-label="ERP Auth System">
      <div className="fp-logo-icon" aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" width="22" height="22">
          <rect width="32" height="32" rx="8" fill="#3b82f6"/>
          <path d="M10 22V14l6-4 6 4v8" stroke="white" strokeWidth="2" strokeLinejoin="round"/>
          <rect x="13" y="17" width="6" height="5" rx="1" stroke="white" strokeWidth="1.5"/>
        </svg>
      </div>
      <span className="fp-logo-text">ERP Auth</span>
    </div>
  );
}

function EyeIcon({ open }) {
  return open ? (
    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24M1 1l22 22" />
    </svg>
  ) : (
    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
      <path d="M5 12h14M12 5l7 7-7 7" />
    </svg>
  );
}

function BackIcon() {
  return (
    <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
      <path d="M19 12H5M12 5l-7 7 7 7" />
    </svg>
  );
}

// 🟡 Fix #3: Progress indicator using STEP_ORDER
function StepProgress({ currentStep }) {
  const currentIndex = STEP_ORDER.indexOf(currentStep);
  if (currentIndex === -1) return null;

  return (
    <div className="fp-progress" role="progressbar" aria-label="Progress" aria-valuenow={currentIndex + 1} aria-valuemax={STEP_ORDER.length}>
      {STEP_ORDER.map((s, i) => (
        <div
          key={s}
          className={`fp-progress-dot ${i <= currentIndex ? "active" : ""} ${i < currentIndex ? "done" : ""}`}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

// ─── Step Components ──────────────────────────────────────────────────────────

function EmailStep({ onSubmit, loading, errors, dispatchError }) {
  const [email, setEmail] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    // FIXED: .toLowerCase() removed — RFC 5321 local-part is case-sensitive. Backend decides.
    const normalized = email.trim();
    if (!normalized || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(normalized)) {
      dispatchError({ type: "SET", field: "email", message: "Please enter a valid work email address" });
      return;
    }
    dispatchError({ type: "CLEAR_ALL" });
    onSubmit(normalized);
  };

  return (
    <div className="fp-step-content">
      <div className="fp-step-icon">
        <svg width="26" height="26" fill="none" viewBox="0 0 24 24" stroke="#3b82f6" strokeWidth="1.8" aria-hidden="true">
          <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
        </svg>
      </div>
      <h1 className="fp-title">Reset your password</h1>
      <p className="fp-subtitle">
        Enter the email address associated with your ERP account and we'll send you a recovery link.
      </p>
      <form onSubmit={handleSubmit} noValidate>
        <div className="fp-field">
          <label htmlFor="fp-email" className="fp-label">Email Address</label>
          <div className="fp-input-wrap">
            <span className="fp-input-icon" aria-hidden="true">
              <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </span>
            <input
              id="fp-email"
              className={`fp-input${errors.email ? " error" : ""}`}
              type="email"
              placeholder="name@company.com"
              value={email}
              onChange={e => { setEmail(e.target.value); dispatchError({ type: "CLEAR", field: "email" }); }}
              autoFocus
              autoComplete="email"
              aria-describedby={errors.email ? "email-error" : undefined}
              aria-invalid={!!errors.email}
            />
          </div>
          {errors.email && (
            <div id="email-error" className="fp-error" role="alert" aria-live="polite">
              ⚠ {errors.email}
            </div>
          )}
        </div>
        <button className="fp-btn" type="submit" disabled={loading} aria-busy={loading}>
          {loading
            ? <><div className="fp-spinner" aria-hidden="true" /><span>Sending...</span></>
            : <>Send Recovery Link <ArrowIcon /></>}
        </button>
      </form>
      <a href="/login" className="fp-back-link"><BackIcon /> Back to Login</a>
    </div>
  );
}

function OtpStep({ email, onSubmit, onBack, loading, errors, dispatchError }) {
  const [otp, setOtp]   = useState(["", "", "", "", "", ""]);
  const inputRefs       = useRef([]);
  const { timer, isRunning, start: startTimer } = useOtpTimer(60);

  // 🔴 Advanced Fix #1: startTimer في dependency array — React rules compliant, no stale closure
  useEffect(() => {
    startTimer();
  }, [startTimer]);

  // 🔴 Fix #1: Safe maskedEmail — handles short names & edge cases
  const maskedEmail = useMemo(() => {
    const [name, domain] = email.split("@");
    if (!name || !domain) return email;
    const visible = name.slice(0, 2);
    const masked  = "*".repeat(Math.max(name.length - 2, 0));
    return `${visible}${masked}@${domain}`;
  }, [email]);

  const handlePaste = useCallback((e) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length === 6) {
      setOtp(pasted.split(""));
      dispatchError({ type: "CLEAR", field: "otp" });
      inputRefs.current[5]?.focus();
    }
  }, [dispatchError]);

  // 🟡 Advanced Fix #2: functional setState — no otp in deps, stable reference, no stale closure
  const handleChange = useCallback((val, idx) => {
    if (!/^\d*$/.test(val)) return;
    setOtp(prev => {
      const next = [...prev];
      next[idx] = val.slice(-1);
      return next;
    });
    dispatchError({ type: "CLEAR", field: "otp" });
    if (val && idx < 5) inputRefs.current[idx + 1]?.focus();
  }, [dispatchError]);

  // otpRef mirrors otp state so handleKeyDown reads fresh value without adding otp to deps
  const otpRef = useRef(["", "", "", "", "", ""]);
  useEffect(() => { otpRef.current = otp; }, [otp]);

  const handleKeyDown = useCallback((e, idx) => {
    if (e.key === "Backspace" && !otpRef.current[idx] && idx > 0) inputRefs.current[idx - 1]?.focus();
  }, []);

  // use otpRef.current for consistent read — no risk of stale closure on submit
  const handleSubmit = (e) => {
    e.preventDefault();
    const current = otpRef.current;
    if (current.some(d => !d)) {
      dispatchError({ type: "SET", field: "otp", message: "Please enter the complete 6-digit code" });
      return;
    }
    dispatchError({ type: "CLEAR_ALL" });
    onSubmit(current.join(""));
  };

  const handleResend = () => {
    setOtp(["", "", "", "", "", ""]);
    dispatchError({ type: "CLEAR_ALL" });
    startTimer();
    inputRefs.current[0]?.focus();
  };

  return (
    <div className="fp-step-content">
      <h1 className="fp-title">Two-Factor Authentication</h1>
      <p className="fp-subtitle">
        Enter the 6-digit verification code sent to{" "}
        <span className="fp-email-highlight">{maskedEmail}</span>
      </p>
      <form onSubmit={handleSubmit} noValidate>
        <div className="fp-otp-row" role="group" aria-label="6-digit verification code">
          {otp.map((d, i) => (
            <input
              key={i}
              ref={el => inputRefs.current[i] = el}
              className={`fp-otp-input${d ? " filled" : ""}${errors.otp ? " otp-error" : ""}`}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={d}
              onChange={e => handleChange(e.target.value, i)}
              onKeyDown={e => handleKeyDown(e, i)}
              onPaste={i === 0 ? handlePaste : undefined}
              autoComplete={i === 0 ? "one-time-code" : "off"}
              aria-label={`Digit ${i + 1} of 6`}
              autoFocus={i === 0}
            />
          ))}
        </div>
        {errors.otp && (
          <div className="fp-error" style={{ justifyContent: "center", marginBottom: 8 }} role="alert" aria-live="polite">
            ⚠ {errors.otp}
          </div>
        )}
        <button className="fp-btn" type="submit" disabled={loading} aria-busy={loading}>
          {loading
            ? <><div className="fp-spinner" aria-hidden="true" /><span>Verifying...</span></>
            : <>Verify <ArrowIcon /></>}
        </button>
      </form>
      <div className="fp-resend">
        Didn't receive the code?{" "}
        <button type="button" className="fp-resend-btn" disabled={isRunning} onClick={handleResend} aria-disabled={isRunning}>
          {isRunning
            ? <span className="fp-timer" aria-live="polite">{`Resend code in ${String(timer).padStart(2, "0")}s`}</span>
            : "Resend code"}
        </button>
      </div>
      <div className="fp-alt-section">
        <div className="fp-alt-divider"><span>ALTERNATIVE METHODS</span></div>
        <div className="fp-alt-row">
          <button type="button" className="fp-alt-btn">
            <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="#3b82f6" strokeWidth="1.8" aria-hidden="true">
              <rect x="5" y="2" width="14" height="20" rx="2"/>
              <path d="M12 18h.01"/>
            </svg>
            <span>Auth App</span>
          </button>
          <button type="button" className="fp-alt-btn">
            <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="#3b82f6" strokeWidth="1.8" aria-hidden="true">
              <path d="M15 7h3a5 5 0 010 10h-3m-6 0H6A5 5 0 016 7h3"/>
              <line x1="8" y1="12" x2="16" y2="12"/>
            </svg>
            <span>Recovery Key</span>
          </button>
        </div>
      </div>
      <button className="fp-back-link" onClick={onBack}><BackIcon /> Back to Login</button>
    </div>
  );
}

function ResetStep({ onSubmit, loading, errors, dispatchError }) {
  const [newPassword, setNewPassword]         = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNew, setShowNew]                 = useState(false);
  const [showConfirm, setShowConfirm]         = useState(false);
  const strength = usePasswordStrength(newPassword);

  const handleSubmit = (e) => {
    e.preventDefault();
    let hasError = false;
    if (newPassword.length < 8) {
      dispatchError({ type: "SET", field: "newPassword", message: "Password must be at least 8 characters" });
      hasError = true;
    }
    if (newPassword !== confirmPassword) {
      dispatchError({ type: "SET", field: "confirmPassword", message: "Passwords do not match" });
      hasError = true;
    }
    if (hasError) return;
    dispatchError({ type: "CLEAR_ALL" });
    onSubmit(newPassword);
  };

  const toggleNew     = useCallback(() => setShowNew(v => !v), []);
  const toggleConfirm = useCallback(() => setShowConfirm(v => !v), []);

  return (
    <div className="fp-step-content">
      <h1 className="fp-title">Reset your password</h1>
      <p className="fp-subtitle">Ensure your new password is secure and unique to this account.</p>
      <form onSubmit={handleSubmit} noValidate>
        <div className="fp-field">
          <label htmlFor="fp-newpw" className="fp-label">New Password</label>
          <div className="fp-input-wrap">
            <span className="fp-input-icon" aria-hidden="true">
              <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2"/>
                <path d="M7 11V7a5 5 0 0110 0v4"/>
              </svg>
            </span>
            <input
              id="fp-newpw"
              className={`fp-input${errors.newPassword ? " error" : ""}`}
              type={showNew ? "text" : "password"}
              placeholder="Enter new password"
              value={newPassword}
              onChange={e => { setNewPassword(e.target.value); dispatchError({ type: "CLEAR", field: "newPassword" }); }}
              autoComplete="new-password"
              autoFocus
              aria-describedby="pw-strength"
              aria-invalid={!!errors.newPassword}
            />
            <button type="button" className="fp-toggle-btn" onClick={toggleNew} aria-label={showNew ? "Hide password" : "Show password"}>
              <EyeIcon open={showNew} />
            </button>
          </div>
          {newPassword && (
            <div className="fp-strength" id="pw-strength" aria-live="polite" aria-label={`Password strength: ${strength.label}`}>
              <div className="fp-strength-bars" aria-hidden="true">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="fp-strength-bar" style={{ background: i <= strength.score ? strength.color : undefined }} />
                ))}
              </div>
              <span className="fp-strength-label" style={{ color: strength.color }}>{strength.label}</span>
            </div>
          )}
          {errors.newPassword && <div className="fp-error" role="alert" aria-live="polite">⚠ {errors.newPassword}</div>}
        </div>
        <div className="fp-field">
          <label htmlFor="fp-confirmpw" className="fp-label">Confirm Password</label>
          <div className="fp-input-wrap">
            <span className="fp-input-icon" aria-hidden="true">
              <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </span>
            <input
              id="fp-confirmpw"
              className={`fp-input${errors.confirmPassword ? " error" : ""}`}
              type={showConfirm ? "text" : "password"}
              placeholder="Repeat new password"
              value={confirmPassword}
              onChange={e => { setConfirmPassword(e.target.value); dispatchError({ type: "CLEAR", field: "confirmPassword" }); }}
              autoComplete="new-password"
              aria-invalid={!!errors.confirmPassword}
            />
            <button type="button" className="fp-toggle-btn" onClick={toggleConfirm} aria-label={showConfirm ? "Hide confirm password" : "Show confirm password"}>
              <EyeIcon open={showConfirm} />
            </button>
          </div>
          {errors.confirmPassword && <div className="fp-error" role="alert" aria-live="polite">⚠ {errors.confirmPassword}</div>}
        </div>
        <button className="fp-btn" type="submit" disabled={loading} aria-busy={loading}>
          {loading
            ? <><div className="fp-spinner" aria-hidden="true" /><span>Resetting...</span></>
            : <>Update Password <ArrowIcon /></>}
        </button>
      </form>
      <a href="/login" className="fp-back-link"><BackIcon /> Back to sign in</a>
    </div>
  );
}

function SuccessStep() {
  return (
    <div className="fp-step-content" style={{ textAlign: "center" }}>
      <div className="fp-success-icon" role="img" aria-label="Success">
        <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="#3b82f6" strokeWidth="2.2" aria-hidden="true">
          <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <h1 className="fp-title">Password Reset!</h1>
      <p className="fp-subtitle" style={{ marginBottom: 0 }}>
        Your password has been updated successfully. You can now sign in with your new credentials.
      </p>
      <a href="/login" className="fp-btn" style={{ textDecoration: "none", marginTop: 22, display: "flex" }}>
        Go to Sign In <ArrowIcon />
      </a>
    </div>
  );
}

// ─── CSS ──────────────────────────────────────────────────────────────────────
const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html, body, #root { width: 100%; height: 100%; }

  /* ── Page layout ── */
  .fp-page {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    background: #f0f4f9;
    font-family: 'Inter', sans-serif;
    padding: 24px 16px 48px;
  }

  /* ── Logo ── */
  .fp-topbar {
    width: 100%;
    max-width: 440px;
    display: flex;
    justify-content: center;
    margin-bottom: 28px;
  }
  .fp-logo { display: flex; align-items: center; gap: 8px; }
  .fp-logo-icon { display: flex; align-items: center; justify-content: center; }
  .fp-logo-text {
    font-size: 15px;
    font-weight: 700;
    color: #1e293b;
    letter-spacing: -0.01em;
  }

  /* ── Card ── */
  .fp-card {
    width: 100%;
    max-width: 400px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 36px 32px 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.05);
    animation: fadeUp 0.4s cubic-bezier(0.16,1,0.3,1) both;
  }

  /* ── Progress indicator (uses STEP_ORDER) ── */
  .fp-progress {
    display: flex;
    justify-content: center;
    gap: 6px;
    margin-bottom: 24px;
  }
  .fp-progress-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #e2e8f0;
    transition: background 0.3s, transform 0.3s;
  }
  .fp-progress-dot.active {
    background: #93c5fd;
    transform: scale(1.15);
  }
  .fp-progress-dot.done {
    background: #3b82f6;
  }

  /* ── Step content ── */
  .fp-step-content { animation: stepFadeIn 0.3s ease both; }

  /* ── Step icon ── */
  .fp-step-icon {
    width: 52px;
    height: 52px;
    background: #eff6ff;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 18px;
  }

  /* ── Typography ── */
  .fp-title {
    text-align: center;
    font-size: 20px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 8px;
    letter-spacing: -0.02em;
  }
  .fp-subtitle {
    text-align: center;
    font-size: 13px;
    color: #64748b;
    line-height: 1.6;
    margin-bottom: 22px;
  }
  .fp-email-highlight { color: #3b82f6; font-weight: 600; }

  /* ── Fields ── */
  .fp-field { margin-bottom: 14px; }
  .fp-label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 6px;
    letter-spacing: 0.01em;
  }
  .fp-input-wrap { position: relative; }
  .fp-input-icon {
    position: absolute;
    left: 11px;
    top: 50%;
    transform: translateY(-50%);
    color: #9ca3af;
    display: flex;
    align-items: center;
    pointer-events: none;
  }
  .fp-input {
    width: 100%;
    background: #fff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 10px 38px 10px 36px;
    color: #0f172a;
    font-size: 13.5px;
    font-family: 'Inter', sans-serif;
    transition: border-color .2s, box-shadow .2s;
    outline: none;
    /* Prevent zoom on iOS */
    -webkit-text-size-adjust: 100%;
  }
  .fp-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.1); }
  .fp-input::placeholder { color: #9ca3af; }
  .fp-input.error { border-color: #ef4444; box-shadow: 0 0 0 3px rgba(239,68,68,0.07); }
  .fp-toggle-btn {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
    transition: color .15s;
    border-radius: 4px;
    /* Touch target */
    min-width: 32px;
    min-height: 32px;
    justify-content: center;
  }
  .fp-toggle-btn:hover { color: #3b82f6; }
  .fp-toggle-btn:focus-visible { outline: 2px solid rgba(59,130,246,0.5); }
  .fp-error {
    font-size: 11.5px;
    color: #ef4444;
    margin-top: 5px;
    display: flex;
    align-items: center;
    gap: 4px;
    line-height: 1.4;
  }

  /* ── Password strength ── */
  .fp-strength { margin-top: 6px; display: flex; align-items: center; gap: 8px; }
  .fp-strength-bars { display: flex; gap: 3px; flex: 1; }
  .fp-strength-bar {
    height: 3px;
    flex: 1;
    border-radius: 2px;
    background: #e5e7eb;
    transition: background .3s;
  }
  .fp-strength-label {
    font-size: 10.5px;
    color: #6b7280;
    min-width: 40px;
    text-align: right;
    font-weight: 600;
  }

  /* ── OTP ── */
  .fp-otp-row {
    display: flex;
    gap: 8px;
    justify-content: center;
    margin-bottom: 14px;
  }
  .fp-otp-input {
    width: 46px;
    height: 52px;
    text-align: center;
    background: #fff;
    border: 1.5px solid #d1d5db;
    border-radius: 10px;
    color: #0f172a;
    font-size: 20px;
    font-weight: 700;
    font-family: 'Inter', sans-serif;
    outline: none;
    caret-color: transparent;
    transition: border-color .2s, box-shadow .2s, transform .15s;
    /* Touch friendly */
    -webkit-text-size-adjust: 100%;
  }
  .fp-otp-input:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
    transform: translateY(-1px);
  }
  .fp-otp-input.filled { border-color: #93c5fd; background: #eff6ff; }
  .fp-otp-input.otp-error { border-color: #fca5a5; }

  /* ── Resend ── */
  .fp-resend {
    text-align: center;
    font-size: 12.5px;
    color: #6b7280;
    margin-top: 4px;
    margin-bottom: 2px;
  }
  .fp-resend-btn {
    background: none;
    border: none;
    color: #3b82f6;
    cursor: pointer;
    font-size: 12.5px;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    padding: 0;
    margin-left: 3px;
  }
  .fp-resend-btn:disabled { color: #9ca3af; cursor: default; }
  .fp-resend-btn:focus-visible { outline: 2px solid rgba(59,130,246,0.5); border-radius: 3px; }
  .fp-timer { color: #3b82f6; font-weight: 600; }

  /* ── Alternative methods ── */
  .fp-alt-section { margin-top: 20px; }
  .fp-alt-divider {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 10px;
    font-weight: 600;
    color: #9ca3af;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 12px;
  }
  .fp-alt-divider::before, .fp-alt-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #e5e7eb;
  }
  .fp-alt-row { display: flex; gap: 10px; }
  .fp-alt-btn {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px 8px;
    border-radius: 10px;
    border: 1px solid #e5e7eb;
    background: #f9fafb;
    cursor: pointer;
    font-size: 11.5px;
    font-weight: 500;
    color: #374151;
    font-family: 'Inter', sans-serif;
    transition: border-color .2s, background .2s, transform .15s;
    /* Touch target */
    min-height: 64px;
  }
  .fp-alt-btn:hover { border-color: #93c5fd; background: #eff6ff; transform: translateY(-1px); }
  .fp-alt-btn:focus-visible { outline: 2px solid rgba(59,130,246,0.5); }

  /* ── Primary button ── */
  .fp-btn {
    width: 100%;
    padding: 12px;
    border: none;
    border-radius: 8px;
    background: #3b82f6;
    color: #fff;
    font-size: 13.5px;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    letter-spacing: 0.01em;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    margin-top: 18px;
    transition: background .2s, transform .15s, box-shadow .2s;
    box-shadow: 0 2px 8px rgba(59,130,246,0.28);
    /* Touch target */
    min-height: 44px;
    -webkit-tap-highlight-color: transparent;
  }
  .fp-btn:hover:not(:disabled) { background: #2563eb; transform: translateY(-1px); box-shadow: 0 4px 14px rgba(59,130,246,0.36); }
  .fp-btn:active:not(:disabled) { transform: translateY(0); }
  .fp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .fp-btn:focus-visible { outline: 2px solid rgba(59,130,246,0.6); outline-offset: 2px; }

  /* ── Spinner ── */
  .fp-spinner {
    width: 15px;
    height: 15px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin .65s linear infinite;
  }

  /* ── Back link ── */
  .fp-back-link {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    margin-top: 14px;
    font-size: 12.5px;
    color: #6b7280;
    text-decoration: none;
    cursor: pointer;
    transition: color .15s;
    background: none;
    border: none;
    font-family: 'Inter', sans-serif;
    width: 100%;
    /* Touch target */
    min-height: 36px;
    -webkit-tap-highlight-color: transparent;
  }
  .fp-back-link:hover { color: #3b82f6; }
  .fp-back-link:focus-visible { outline: 2px solid rgba(59,130,246,0.5); border-radius: 4px; }

  /* ── Success ── */
  .fp-success-icon {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 18px;
    animation: successPop .5s cubic-bezier(0.34,1.56,0.64,1) both;
  }

  /* ── Footer ── */
  .fp-footer {
    margin-top: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: #9ca3af;
    text-align: center;
  }
  .fp-links { display: flex; gap: 14px; }
  .fp-links a {
    color: #9ca3af;
    text-decoration: none;
    font-size: 11px;
    transition: color .15s;
    padding: 4px 2px; /* better tap target */
  }
  .fp-links a:hover { color: #3b82f6; }

  /* ── Keyframes ── */
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes stepFadeIn {
    from { opacity: 0; transform: translateX(8px); }
    to   { opacity: 1; transform: translateX(0); }
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes successPop {
    0%   { transform: scale(0.5); opacity: 0; }
    70%  { transform: scale(1.08); }
    100% { transform: scale(1);   opacity: 1; }
  }

  /* ──────────────────────────────────────────────────────
     RESPONSIVE: Mobile-first, then upscale
  ────────────────────────────────────────────────────── */

  /* ── Extra-small phones (< 360px) ── */
  @media (max-width: 359px) {
    .fp-page { padding: 16px 10px 32px; }
    .fp-card { padding: 22px 14px 18px; border-radius: 12px; }
    .fp-title { font-size: 17px; }
    .fp-subtitle { font-size: 12px; }
    .fp-otp-input { width: 36px; height: 42px; font-size: 16px; border-radius: 8px; }
    .fp-otp-row { gap: 4px; }
    .fp-input { font-size: 13px; }
    .fp-btn { font-size: 13px; padding: 11px; }
    .fp-logo-text { font-size: 13px; }
  }

  /* ── Small phones (360px – 479px) ── */
  @media (min-width: 360px) and (max-width: 479px) {
    .fp-page { padding: 20px 12px 36px; }
    .fp-card { padding: 26px 18px 20px; }
    .fp-otp-input { width: 40px; height: 46px; font-size: 17px; }
    .fp-otp-row { gap: 6px; }
  }

  /* ── All phones (< 480px) ── */
  @media (max-width: 479px) {
    /* Prevent iOS from auto-zooming on focus */
    .fp-input, .fp-otp-input {
      font-size: 16px !important;
    }
    /* Make alt buttons stack vertically on tiny screens */
    .fp-alt-row { flex-direction: column; }
    .fp-alt-btn { flex-direction: row; justify-content: center; gap: 10px; padding: 12px 16px; }
    /* Widen card to use more screen estate */
    .fp-card { max-width: 100%; }
  }

  /* ── Tablet (768px – 1023px) ── */
  @media (min-width: 768px) and (max-width: 1023px) {
    .fp-page { padding: 40px 24px 60px; }
    .fp-card {
      max-width: 440px;
      padding: 42px 38px 34px;
      border-radius: 20px;
    }
    .fp-topbar { margin-bottom: 36px; }
    .fp-title { font-size: 22px; }
    .fp-subtitle { font-size: 14px; }
    .fp-otp-input { width: 52px; height: 58px; font-size: 22px; }
    .fp-otp-row { gap: 10px; }
    .fp-input { font-size: 14px; padding: 11px 38px 11px 36px; }
    .fp-btn { font-size: 14px; padding: 13px; }
    .fp-label { font-size: 13px; }
  }

  /* ── Desktop (≥ 1024px) ── */
  @media (min-width: 1024px) {
    .fp-page {
      padding: 60px 32px 80px;
      /* subtle grid pattern background */
      background-image:
        linear-gradient(rgba(59,130,246,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(59,130,246,0.03) 1px, transparent 1px);
      background-size: 40px 40px;
    }
    .fp-card {
      max-width: 420px;
      padding: 44px 40px 36px;
      border-radius: 20px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.08);
    }
    .fp-topbar { margin-bottom: 40px; }
    .fp-logo-text { font-size: 16px; }
    .fp-title { font-size: 22px; }
    .fp-subtitle { font-size: 14px; }
    .fp-input { font-size: 14px; padding: 11px 40px 11px 38px; }
    .fp-btn { font-size: 14px; padding: 13px; }
    .fp-label { font-size: 12.5px; }
    .fp-otp-input { width: 50px; height: 56px; font-size: 22px; }
    .fp-otp-row { gap: 10px; }
  }

  /* ── Large desktop (≥ 1440px) ── */
  @media (min-width: 1440px) {
    .fp-page { padding: 80px 32px 100px; }
    .fp-card { max-width: 440px; padding: 48px 44px 40px; }
  }

  /* ── Print ── */
  @media print {
    .fp-page { background: white; padding: 0; }
    .fp-card { box-shadow: none; border: 1px solid #ccc; }
    .fp-btn, .fp-back-link, .fp-resend-btn, .fp-alt-btn { display: none; }
  }

  /* ── High contrast / accessibility ── */
  @media (prefers-contrast: high) {
    .fp-input { border-width: 2px; }
    .fp-otp-input { border-width: 2px; }
    .fp-btn { background: #1d4ed8; }
  }

  /* ── Reduced motion ── */
  @media (prefers-reduced-motion: reduce) {
    .fp-card, .fp-step-content, .fp-success-icon,
    .fp-otp-input, .fp-btn, .fp-alt-btn { animation: none !important; transition: none !important; }
    .fp-spinner { animation: spin 1.2s linear infinite; }
  }
`;

// ─── Flow Reducer (Advanced Fix #4) ──────────────────────────────────────────
// Enterprise-grade navigation: predictable, debuggable, testable.
// NEXT/BACK traverse STEP_ORDER. SET_EMAIL saves email alongside nav.
// SUCCESS is outside STEP_ORDER (terminal state, no back).
function flowReducer(state, action) {
  switch (action.type) {
    case "NEXT": {
      const idx = STEP_ORDER.indexOf(state.step);
      const nextStep = idx < STEP_ORDER.length - 1 ? STEP_ORDER[idx + 1] : STEPS.SUCCESS;
      return { ...state, step: nextStep };
    }
    case "BACK": {
      const idx = STEP_ORDER.indexOf(state.step);
      const prevStep = idx > 0 ? STEP_ORDER[idx - 1] : state.step;
      return { ...state, step: prevStep };
    }
    case "SET_EMAIL":
      return { ...state, email: action.email };
    case "RESET":
      return flowInitialState;
    default:
      return state;
  }
}

const flowInitialState = { step: STEPS.EMAIL, email: "" };

// ─── Main Component ───────────────────────────────────────────────────────────
export default function ForgotPassword() {
  // 🔥 Advanced Fix #4: useReducer للـ flow navigation — predictable, testable, Enterprise-grade
  const [flow, dispatch]        = useReducer(flowReducer, flowInitialState);
  const { step, email }         = flow;

  const [loading, setLoading]   = useState(false);
  const [errors, dispatchError] = useReducer(errorReducer, {});

  // Production cleanup — cancel pending setTimeout on unmount
  const timeoutRef = useRef();

  const simulateRequest = useCallback((cb) => {
    setLoading(true);
    timeoutRef.current = setTimeout(() => {
      setLoading(false);
      cb();
    }, 1500);
  }, []);

  useEffect(() => {
    return () => clearTimeout(timeoutRef.current);
  }, []);

  const handleEmailSubmit = useCallback(
    (e) => simulateRequest(() => {
      dispatch({ type: "SET_EMAIL", email: e });
      dispatch({ type: "NEXT" });
    }),
    [simulateRequest]
  );
  const handleOtpSubmit   = useCallback(
    () => simulateRequest(() => dispatch({ type: "NEXT" })),
    [simulateRequest]
  );
  const handleResetSubmit = useCallback(
    () => simulateRequest(() => dispatch({ type: "NEXT" })),
    [simulateRequest]
  );

  // 🟡 Advanced Fix #3: useMemo — stepComponents لا تتعمل من جديد في كل render
  const stepComponents = useMemo(() => ({
    [STEPS.EMAIL]: (
      <EmailStep
        onSubmit={handleEmailSubmit}
        loading={loading}
        errors={errors}
        dispatchError={dispatchError}
      />
    ),
    [STEPS.OTP]: (
      <OtpStep
        email={email}
        onSubmit={handleOtpSubmit}
        onBack={() => dispatch({ type: "BACK" })}
        loading={loading}
        errors={errors}
        dispatchError={dispatchError}
      />
    ),
    [STEPS.RESET]: (
      <ResetStep
        onSubmit={handleResetSubmit}
        loading={loading}
        errors={errors}
        dispatchError={dispatchError}
      />
    ),
    [STEPS.SUCCESS]: <SuccessStep />,
  }), [email, loading, errors, handleEmailSubmit, handleOtpSubmit, handleResetSubmit, dispatchError]);

  return (
    <>
      <style>{styles}</style>
      <div className="fp-page">

        <div className="fp-topbar">
          <Logo />
        </div>

        <main className="fp-card" role="main">
          {/* Progress dots (only during active steps, not success) */}
          <StepProgress currentStep={step} />

          {/* 🔥 Fix #5: Map-based step rendering */}
          <div key={step}>
            {stepComponents[step]}
          </div>
        </main>

        <footer className="fp-footer">
          <div>© 2024 ERP Auth System</div>
          <nav className="fp-links" aria-label="Footer links">
            <a href="/privacy">Privacy Policy</a>
            <a href="/terms">Terms of Service</a>
          </nav>
        </footer>

      </div>
    </>
  );
}