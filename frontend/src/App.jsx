import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AuthPage from "./components/AuthPage";
import Sidebar from "./components/Sidebar";
import AdminPanel from "./components/AdminPanel";
import { getCurrentAccount } from "./services/authApi";

const AnalysesPage = lazy(() => import("./pages/AnalysesPage"));
const NewAnalysisPage = lazy(() => import("./pages/NewAnalysisPage"));
const AnalysisPage = lazy(() => import("./pages/AnalysisPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));

const TOKEN_KEY = "alphaToken";

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [account, setAccount] = useState(null);
  const [authStatus, setAuthStatus] = useState(token ? "checking" : "signed-out");

  useEffect(() => {
    if (!token) return;
    let active = true;
    getCurrentAccount(token).then((response) => {
      if (!active) return;
      setAccount(response.data.account);
      setAuthStatus("signed-in");
    }).catch(() => {
      if (!active) return;
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setAccount(null);
      setAuthStatus("signed-out");
    });
    return () => { active = false; };
  }, [token]);

  function handleAuthenticated(authData) {
    localStorage.setItem(TOKEN_KEY, authData.token);
    setToken(authData.token);
    setAccount(authData.account);
    setAuthStatus("signed-in");
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setAccount(null);
    setAuthStatus("signed-out");
  }

  if (authStatus === "checking") return <div className="auth-loading">Checking your session...</div>;
  if (authStatus !== "signed-in") return <AuthPage onAuthenticated={handleAuthenticated}/>;
  if (account?.role === "admin") return <AdminPanel token={token} account={account} onLogout={handleLogout}/>;

  const accountLabel = account?.businessName || account?.email || "Business Account";
  const initials = accountLabel.slice(0, 2).toUpperCase();

  return <div className="app-shell">
    <Sidebar/>
    <main className="main-content">
      <header className="topbar">
        <div className="mobile-brand"><span>A</span>Alpha</div>
        <div className="account-area">
          <div className="account-avatar">{initials}</div>
          <div><strong>{accountLabel}</strong><span><i/>Signed in</span></div>
          <button className="logout-button" type="button" onClick={handleLogout}>Sign out</button>
        </div>
      </header>
      <Suspense fallback={<div className="page-content"><div className="analytics-loading"><span className="spinner"/>Loading…</div></div>}>
        <Routes>
          <Route path="/" element={<Navigate to="/analyses" replace/>}/>
          <Route path="/analyses" element={<AnalysesPage token={token}/>}/>
          <Route path="/upload" element={<NewAnalysisPage token={token}/>}/>
          <Route path="/analysis/:id" element={<AnalysisPage token={token}/>}/>
          <Route path="/settings" element={<SettingsPage token={token}/>}/>
          <Route path="*" element={<Navigate to="/analyses" replace/>}/>
        </Routes>
      </Suspense>
    </main>
  </div>;
}
