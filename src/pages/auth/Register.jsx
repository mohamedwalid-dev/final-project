import { useState, useEffect } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import s from "./Auth.module.css";

export default function Register() {
  const navigate = useNavigate();
  const location = useLocation();
  const { register, user, loading: authLoading } = useAuth();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [validationErrors, setValidationErrors] = useState({});
  const [agreedToTerms, setAgreedToTerms] = useState(false);

  // Redirect if already logged in
  useEffect(() => {
    if (!authLoading && user) {
      const from = location.state?.from?.pathname || "/dashboard";
      navigate(from, { replace: true });
    }
  }, [user, authLoading, navigate, location]);

  if (authLoading) {
    return (
      <div className={s.container}>
        <div className={s.spinner} />
      </div>
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setValidationErrors({});
    setLoading(true);

    // Validate
    const errors = {};
    if (!firstName || firstName.trim().length === 0) {
      errors.first_name = "First name is required";
    }
    if (!lastName || lastName.trim().length === 0) {
      errors.last_name = "Last name is required";
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = "Valid email is required";
    }
    if (!password || password.length < 8) {
      errors.password = "Password must be at least 8 characters";
    }
    if (password !== confirmPassword) {
      errors.confirmPassword = "Passwords do not match";
    }
    if (!agreedToTerms) {
      errors.terms = "You must agree to the terms and conditions";
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      setLoading(false);
      return;
    }

    const result = await register({
      first_name: firstName,
      last_name: lastName,
      email,
      password,
    });

    if (result.error) {
      setError(result.error);
      if (result.errorData && Array.isArray(result.errorData)) {
        const newErrors = {};
        result.errorData.forEach((err) => {
          if (err.path) newErrors[err.path] = err.msg;
        });
        setValidationErrors(newErrors);
      }
      setLoading(false);
      return;
    }

    // Success - redirect
    navigate("/dashboard", { replace: true });
  };

  return (
    <div className={s.authPage}>
      <div className={s.container}>
        <div className={s.card}>
          <div className={s.header}>
            <h1 className={s.title}>Create Account</h1>
            <p className={s.subtitle}>Join Prime and manage your business</p>
          </div>

          {error && <div className={s.errorAlert}>{error}</div>}

          <form onSubmit={handleSubmit} className={s.form}>
            <div className={s.formRow}>
              <div className={s.formGroup}>
                <label htmlFor="firstName" className={s.label}>
                  First Name
                </label>
                <input
                  id="firstName"
                  type="text"
                  className={`${s.input} ${validationErrors.first_name ? s.inputError : ""}`}
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="John"
                  disabled={loading}
                />
                {validationErrors.first_name && (
                  <p className={s.fieldError}>{validationErrors.first_name}</p>
                )}
              </div>

              <div className={s.formGroup}>
                <label htmlFor="lastName" className={s.label}>
                  Last Name
                </label>
                <input
                  id="lastName"
                  type="text"
                  className={`${s.input} ${validationErrors.last_name ? s.inputError : ""}`}
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Doe"
                  disabled={loading}
                />
                {validationErrors.last_name && (
                  <p className={s.fieldError}>{validationErrors.last_name}</p>
                )}
              </div>
            </div>

            <div className={s.formGroup}>
              <label htmlFor="email" className={s.label}>
                Email Address
              </label>
              <input
                id="email"
                type="email"
                className={`${s.input} ${validationErrors.email ? s.inputError : ""}`}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={loading}
              />
              {validationErrors.email && (
                <p className={s.fieldError}>{validationErrors.email}</p>
              )}
            </div>

            <div className={s.formRow}>
              <div className={s.formGroup}>
                <label htmlFor="password" className={s.label}>
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  className={`${s.input} ${validationErrors.password ? s.inputError : ""}`}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  disabled={loading}
                />
                {validationErrors.password && (
                  <p className={s.fieldError}>{validationErrors.password}</p>
                )}
              </div>

              <div className={s.formGroup}>
                <label htmlFor="confirmPassword" className={s.label}>
                  Confirm Password
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  className={`${s.input} ${validationErrors.confirmPassword ? s.inputError : ""}`}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  disabled={loading}
                />
                {validationErrors.confirmPassword && (
                  <p className={s.fieldError}>{validationErrors.confirmPassword}</p>
                )}
              </div>
            </div>

            <div className={s.checkboxGroup}>
              <input
                id="terms"
                type="checkbox"
                className={s.checkbox}
                checked={agreedToTerms}
                onChange={(e) => setAgreedToTerms(e.target.checked)}
                disabled={loading}
              />
              <label htmlFor="terms" className={s.checkboxLabel}>
                I agree to the terms and conditions
              </label>
              {validationErrors.terms && (
                <p className={s.fieldError} style={{ display: "block", marginTop: "6px" }}>
                  {validationErrors.terms}
                </p>
              )}
            </div>

            <button type="submit" className={s.submitBtn} disabled={loading}>
              {loading ? (
                <>
                  <span className={s.spinner} />
                  Creating account...
                </>
              ) : (
                "Create Account"
              )}
            </button>
          </form>

          <div className={s.divider}>Or</div>

          <p className={s.footer}>
            Already have an account?{" "}
            <Link to="/login" className={s.link}>
              Sign in
            </Link>
          </p>
        </div>

        <div className={s.illustration}>
          <div className={s.illustrationBox}>
            <div className={s.illustrationCircle} />
            <div className={s.illustrationText}>
              <p>Prime ERP</p>
              <p style={{ fontSize: "12px", opacity: 0.7, marginTop: "4px" }}>
                Enterprise Resource Planning System
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
