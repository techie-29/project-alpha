import { useState } from "react";
import { loginBusiness, registerBusiness } from "../services/authApi";
import "./AuthPage.css";

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const isRegistering = mode === "register";

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const payload = isRegistering
        ? await registerBusiness({ businessName, email, password })
        : await loginBusiness({ email, password });

      onAuthenticated(payload.data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function switchMode() {
    setMode(isRegistering ? "login" : "register");
    setError("");
  }

  return <main className="auth-page">
    <section className="auth-hero">
      <span className="eyebrow">Explainable business intelligence</span>
      <h1>From imperfect files to decisions you can verify.</h1>
      <p>Project Alpha maps, validates, transforms, and analyzes sales and inventory data without hiding the source evidence.</p>
      <div className="auth-pipeline"><span>Upload</span><i/> <span>Validate</span><i/> <span>Analyze</span><i/> <span>Act</span></div>
      <ul><li>Adaptive KPIs—no invented zeroes</li><li>Metric-to-source traceability</li><li>Forecasts with measured backtest error</li></ul>
    </section>
    <section className="auth-card">
      <div className="auth-brand"><span>A</span><div><strong>Project Alpha</strong><small>Business Intelligence</small></div></div>
      <span className="eyebrow">Module 01 / Authentication</span>
      <h1>{isRegistering ? "Create business account" : "Welcome back"}</h1>
      <p>{isRegistering ? "Register your business to begin using the Alpha data pipeline." : "Sign in to access your secure data-ingestion workspace."}</p>

      <form onSubmit={handleSubmit}>
        {isRegistering && <label>Business name<input type="text" value={businessName} onChange={(event) => setBusinessName(event.target.value)} autoComplete="organization" required/></label>}
        <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required/></label>
        <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={isRegistering ? "new-password" : "current-password"} minLength={isRegistering ? 8 : 1} maxLength="128" required/></label>

        {error && <div className="auth-error" role="alert">{error}</div>}

        <button className="auth-submit" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Please wait..." : isRegistering ? "Create account" : "Sign in"}
        </button>
      </form>

      <button className="auth-switch" type="button" onClick={switchMode} disabled={isSubmitting}>
        {isRegistering ? "Already have an account? Sign in" : "New to Alpha? Create an account"}
      </button>
    </section>
  </main>;
}
