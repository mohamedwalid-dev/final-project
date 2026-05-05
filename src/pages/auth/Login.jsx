import { useState, useEffect } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import s from "./Auth.module.css";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, user, loading: authLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [validationErrors, setValidationErrors] = useState({});

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
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = "Valid email is required";
    }
    if (!password || password.length < 8) {
      errors.password = "Password must be at least 8 characters";
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      setLoading(false);
      return;
    }

    const result = await login({ email, password });
    
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
    const from = location.state?.from?.pathname || "/dashboard";
    navigate(from, { replace: true });
  };

  return (
    <div className={s.authPage}>
      <div className={s.container}>
        <div className={s.card}>
          <div className={s.header}>
            <h1 className={s.title}>Welcome Back</h1>
            <p className={s.subtitle}>Sign in to your Synergy account</p>
          </div>

          {error && <div className={s.errorAlert}>{error}</div>}

          <form onSubmit={handleSubmit} className={s.form}>
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

            <div className={s.formGroup}>
              <div className={s.labelRow}>
                <label htmlFor="password" className={s.label}>
                  Password
                </label>
                <Link to="/forgot-password" className={s.forgotLink}>
                  Forgot?
                </Link>
              </div>
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

            <button type="submit" className={s.submitBtn} disabled={loading}>
              {loading ? (
                <>
                  <span className={s.spinner} />
                  Signing in...
                </>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          <div className={s.divider}>Or</div>

          <p className={s.footer}>
            Don't have an account?{" "}
            <Link to="/register" className={s.link}>
              Create one
            </Link>
          </p>
        </div>

        <div className={s.illustration}>
          <div className={s.illustrationBox}>
            <div className={s.illustrationCircle} />
            <div className={s.illustrationText}>
              <p>Synergy ERP</p>
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
