import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AuthPage from "./components/AuthPage";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import { AnalysisProvider, useAnalysis } from "./context/AnalysisContext";
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

  return <AnalysisProvider token={token}><Shell token={token} accountLabel={accountLabel} onLogout={handleLogout}/></AnalysisProvider>;
}

function Shell({ token, accountLabel, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return <div className="app-shell">
    <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)}/>
    {menuOpen && <button type="button" className="sidebar-scrim" aria-label="Close menu" onClick={() => setMenuOpen(false)}/>}
    <main className="main-content">
      <TopBar accountLabel={accountLabel} onLogout={onLogout} onMenu={() => setMenuOpen(true)}/>
      <Suspense fallback={<div className="page-content"><div className="analytics-loading"><span className="spinner"/>Loading…</div></div>}>
        <Routes>
          <Route path="/" element={<Home/>}/>
          <Route path="/analyses" element={<AnalysesPage token={token}/>}/>
          <Route path="/upload" element={<NewAnalysisPage token={token}/>}/>
          <Route path="/analysis/:id" element={<AnalysisPage/>}/>
          <Route path="/analysis/:id/:section" element={<AnalysisPage/>}/>
          <Route path="/settings" element={<SettingsPage token={token}/>}/>
          <Route path="*" element={<Navigate to="/analyses" replace/>}/>
        </Routes>
      </Suspense>
    </main>
  </div>;
}

/** Open the owner's latest analysis; with none yet, start with an upload. */
function Home() {
  const { analyses, currentId } = useAnalysis();
  if (!analyses) return <div className="page-content"><div className="analytics-loading"><span className="spinner"/>Loading…</div></div>;
  return <Navigate to={currentId ? `/analysis/${currentId}/overview` : "/upload"} replace/>;
}
