import React, { useState, useCallback, useId } from "react";
import { useNavigate } from "react-router-dom";
import "./LoginPage.css";

// ─── SVG Icon Components ────────────────────────────────────────────────────

const ShieldIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M12 2L4 6v6c0 5.25 3.5 10.15 8 11.35C16.5 22.15 20 17.25 20 12V6L12 2z"
      fill="currentColor"
      opacity="0.9"
    />
    <path
      d="M9 12l2 2 4-4"
      stroke="white"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const EnvelopeIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="2" y="4" width="20" height="16" rx="2" stroke="currentColor" strokeWidth="1.8" />
    <path d="M2 7l10 7 10-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

const LockIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="5" y="11" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.8" />
    <path
      d="M8 11V7a4 4 0 018 0v4"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
  </svg>
);

const EyeIcon = ({ open }) =>
  open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"
        stroke="currentColor"
        strokeWidth="1.8"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19M1 1l22 22"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      fill="#4285F4"
    />
    <path
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      fill="#34A853"
    />
    <path
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
      fill="#FBBC05"
    />
    <path
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      fill="#EA4335"
    />
  </svg>
);

const AzureIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M13.05 2L6 13.5l4.5 1.5L5 22h14l-2-3.5-4-1.5L18 8l-4.95-6z" fill="#0078D4" />
  </svg>
);

const LockOutlineIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="5" y="11" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.8" />
    <path
      d="M8 11V7a4 4 0 018 0v4"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
  </svg>
);

const ChevronRightIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M9 18l6-6-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// ─── Validation Helpers ─────────────────────────────────────────────────────

const VALIDATORS = {
  email: (value) => {
    if (!value.trim()) return "Email address is required.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Please enter a valid email address.";
    return null;
  },
  password: (value) => {
    if (!value) return "Password is required.";
    if (value.length < 6) return "Password must be at least 6 characters.";
    return null;
  },
};

// ─── Sub-Components ─────────────────────────────────────────────────────────

const InputField = ({
  id,
  label,
  type = "text",
  value,
  onChange,
  onBlur,
  placeholder,
  error,
  icon,
  rightElement,
  autoComplete,
  required = false,
  disabled = false,
}) => (
  <div className={`erp-field${error ? " erp-field--error" : ""}`}>
    <label className="erp-field__label" htmlFor={id}>
      {label}
    </label>
    <div className="erp-field__wrapper">
      {icon && <span className="erp-field__icon erp-field__icon--left">{icon}</span>}
      <input
        id={id}
        className={`erp-field__input${icon ? " erp-field__input--with-left-icon" : ""}${
          rightElement ? " erp-field__input--with-right-icon" : ""
        }`}
        type={type}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        disabled={disabled}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {rightElement && (
        <span className="erp-field__icon erp-field__icon--right">{rightElement}</span>
      )}
    </div>
    {error && (
      <p id={`${id}-error`} className="erp-field__error" role="alert">
        {error}
      </p>
    )}
  </div>
);

// ─── Main Component ─────────────────────────────────────────────────────────

/**
 * LoginPage — Production-ready ERP authentication page.
 *
 * Props:
 *   onLogin        (email, password, rememberMe) => Promise<void>  — submit handler
 *   onGoogleLogin  () => void
 *   onAzureLogin   () => void
 *   onForgotPassword () => void
 *   onCreateAccount  () => void
 *   logoText       string  (default: "ERP Auth")
 *   isLoading      boolean — external loading override
 */
const LoginPage = ({
  onLogin,
  onGoogleLogin,
  onAzureLogin,
  onForgotPassword,
  onCreateAccount,
  logoText = "ERP Auth",
  isLoading: externalLoading = false,
}) => {
  const navigate = useNavigate();

  // ── State ──────────────────────────────────────────────────────────────────
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [azureLoading, setAzureLoading] = useState(false);

  // Accessible IDs (React 18 useId — collision-safe in SSR too)
  const emailId = useId();
  const passwordId = useId();
  const rememberMeId = useId();

  const isLoading = externalLoading || submitting || googleLoading || azureLoading;

  // ── Validation ─────────────────────────────────────────────────────────────
  const validateField = useCallback((name, value) => {
    const validator = VALIDATORS[name];
    return validator ? validator(value) : null;
  }, []);

  const validateAll = useCallback(() => {
    const emailError = VALIDATORS.email(email);
    const passwordError = VALIDATORS.password(password);
    const newErrors = {};
    if (emailError) newErrors.email = emailError;
    if (passwordError) newErrors.password = passwordError;
    setErrors(newErrors);
    setTouched({ email: true, password: true });
    return Object.keys(newErrors).length === 0;
  }, [email, password]);

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleFieldChange = useCallback(
    (field, setter) => (e) => {
      const val = e.target.value;
      setter(val);
      setSubmitError(null);
      if (touched[field]) {
        const err = validateField(field, val);
        setErrors((prev) => ({ ...prev, [field]: err || undefined }));
      }
    },
    [touched, validateField]
  );

  const handleBlur = useCallback(
    (field, value) => () => {
      setTouched((prev) => ({ ...prev, [field]: true }));
      const err = validateField(field, value);
      setErrors((prev) => ({ ...prev, [field]: err || undefined }));
    },
    [validateField]
  );

  const handleSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      setSubmitError(null);
      if (!validateAll()) return;

      setSubmitting(true);
      try {
        await onLogin?.(email.trim().toLowerCase(), password, rememberMe);
        navigate("/dashboard", { replace: true });   // ← الـ redirect بعد Login
      } catch (err) {
        setSubmitError(
          err?.message || "Invalid credentials. Please check your email and password."
        );
      } finally {
        setSubmitting(false);
      }
    },
    [email, password, rememberMe, validateAll, onLogin]
  );

  const handleGoogleLogin = useCallback(async () => {
    if (isLoading) return;
    setGoogleLoading(true);
    setSubmitError(null);
    try {
      await onGoogleLogin?.();
    } catch (err) {
      setSubmitError(err?.message || "Google sign-in failed. Please try again.");
    } finally {
      setGoogleLoading(false);
    }
  }, [isLoading, onGoogleLogin]);

  const handleAzureLogin = useCallback(async () => {
    if (isLoading) return;
    setAzureLoading(true);
    setSubmitError(null);
    try {
      await onAzureLogin?.();
    } catch (err) {
      setSubmitError(err?.message || "Azure AD sign-in failed. Please try again.");
    } finally {
      setAzureLoading(false);
    }
  }, [isLoading, onAzureLogin]);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="erp-page" role="main">
      {/* Background decorative blobs */}
      <div className="erp-page__blob erp-page__blob--1" aria-hidden="true" />
      <div className="erp-page__blob erp-page__blob--2" aria-hidden="true" />

      <div className="erp-container">
        {/* ── Brand Header ── */}
        <header className="erp-brand" aria-label="ERP Auth">
          <div className="erp-brand__logo" aria-hidden="true">
            <ShieldIcon />
          </div>
          <span className="erp-brand__name">{logoText}</span>
        </header>

        {/* ── Hero Text ── */}
        <div className="erp-hero">
          <h1 className="erp-hero__title">Welcome back</h1>
          <p className="erp-hero__subtitle">
            Access your secure ERP workspace and manage
            <br />
            your enterprise data with ease.
          </p>
        </div>

        {/* ── Card ── */}
        <div className="erp-card" role="region" aria-label="Login form">
          {/* Global submit error */}
          {submitError && (
            <div className="erp-alert erp-alert--error" role="alert" aria-live="assertive">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8" />
                <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
              {submitError}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate aria-label="Sign in to your workspace">
            {/* Email */}
            <InputField
              id={emailId}
              label="Email Address"
              type="email"
              value={email}
              onChange={handleFieldChange("email", setEmail)}
              onBlur={handleBlur("email", email)}
              placeholder="name@company.com"
              error={touched.email ? errors.email : undefined}
              icon={<EnvelopeIcon />}
              autoComplete="email"
              required
              disabled={isLoading}
            />

            {/* Password */}
            <InputField
              id={passwordId}
              label="Password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={handleFieldChange("password", setPassword)}
              onBlur={handleBlur("password", password)}
              placeholder="••••••••"
              error={touched.password ? errors.password : undefined}
              icon={<LockIcon />}
              rightElement={
                <button
                  type="button"
                  className="erp-field__toggle"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  tabIndex={0}
                  disabled={isLoading}
                >
                  <EyeIcon open={showPassword} />
                </button>
              }
              autoComplete="current-password"
              required
              disabled={isLoading}
            />

            {/* Options row */}
            <div className="erp-options">
              <label className="erp-checkbox" htmlFor={rememberMeId}>
                <input
                  id={rememberMeId}
                  type="checkbox"
                  className="erp-checkbox__input"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  disabled={isLoading}
                />
                <span className="erp-checkbox__box" aria-hidden="true" />
                <span className="erp-checkbox__label">Remember for 30 days</span>
              </label>

              <button
                type="button"
                className="erp-link"
                onClick={onForgotPassword}
                disabled={isLoading}
              >
                Forgot password?
              </button>
            </div>

            {/* Submit */}
            <button
              type="submit"
              className={`erp-btn erp-btn--primary${submitting ? " erp-btn--loading" : ""}`}
              disabled={isLoading}
              aria-busy={submitting}
            >
              {submitting ? (
                <>
                  <span className="erp-btn__spinner" aria-hidden="true" />
                  <span>Signing in…</span>
                </>
              ) : (
                <>
                  <span>Login to Workspace</span>
                  <ChevronRightIcon />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="erp-divider" aria-hidden="true">
            <span>OR CONTINUE WITH</span>
          </div>

          {/* SSO Buttons */}
          <div className="erp-sso">
            <button
              type="button"
              className={`erp-btn erp-btn--sso${googleLoading ? " erp-btn--loading" : ""}`}
              onClick={handleGoogleLogin}
              disabled={isLoading}
              aria-label="Continue with Google"
              aria-busy={googleLoading}
            >
              {googleLoading ? (
                <span className="erp-btn__spinner erp-btn__spinner--dark" aria-hidden="true" />
              ) : (
                <GoogleIcon />
              )}
              <span>Google</span>
            </button>

            <button
              type="button"
              className={`erp-btn erp-btn--sso${azureLoading ? " erp-btn--loading" : ""}`}
              onClick={handleAzureLogin}
              disabled={isLoading}
              aria-label="Continue with Azure AD"
              aria-busy={azureLoading}
            >
              {azureLoading ? (
                <span className="erp-btn__spinner erp-btn__spinner--dark" aria-hidden="true" />
              ) : (
                <AzureIcon />
              )}
              <span>Azure AD</span>
            </button>
          </div>

          {/* Create account */}
          <p className="erp-card__footer-text">
            New to ERP system?{" "}
            <button type="button" className="erp-link" onClick={onCreateAccount} disabled={isLoading}>
              Create an account
            </button>
          </p>
        </div>

        {/* ── Security note ── */}
        <p className="erp-security-note" aria-label="Security information">
          <LockOutlineIcon />
          Secure, bank-grade encryption in transit.
        </p>

        {/* ── Footer ── */}
        <footer className="erp-footer">
          <span>© {new Date().getFullYear()} ERP Auth System</span>
          <button type="button" className="erp-link erp-link--muted">Privacy Policy</button>
          <button type="button" className="erp-link erp-link--muted">Terms of Service</button>
        </footer>
      </div>
    </div>
  );
};

export default LoginPage;