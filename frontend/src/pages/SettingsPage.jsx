import { useEffect, useState } from "react";
import { changePassword, getSettings, updateSettings } from "../services/settingsApi";

export default function SettingsPage({ token }) {
  const [settings, setSettings] = useState(null);
  const [passwords, setPasswords] = useState({ currentPassword: "", newPassword: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; getSettings(token).then((response) => active && setSettings(response.data)).catch((requestError) => active && setError(requestError.message)); return () => { active = false; }; }, [token]);
  function field(name, value) { setSettings((current) => ({ ...current, [name]: value })); }
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try { const response = await updateSettings({ businessName: settings.businessName, currencyCode: settings.currencyCode, timezone: settings.timezone, dateFormat: settings.dateFormat }, token); setSettings(response.data); setMessage("Business settings saved."); } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  }
  async function savePassword(event) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try { await changePassword(passwords, token); setPasswords({ currentPassword: "", newPassword: "" }); setMessage("Password updated."); } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  }
  return <div className="page-content analytics-page"><section className="page-header"><span className="eyebrow">Business settings</span><h1>Workspace preferences</h1><p>Manage your profile, display conventions, and account password.</p></section>{error && <div className="analytics-error">{error}</div>}{message && <div className="settings-success">{message}</div>}{!settings && !error && <div className="analytics-loading"><span className="spinner"/>Loading settings…</div>}{settings && <div className="settings-grid"><form className="analytics-card settings-form" onSubmit={save}><div className="analytics-card-heading"><div><span className="eyebrow">Profile and region</span><h2>Business preferences</h2></div></div><div className="settings-fields"><label>Business name<input value={settings.businessName} onChange={(event) => field("businessName", event.target.value)} minLength="2" maxLength="120" required/></label><label>Email<input value={settings.email} disabled/></label><label>Currency<select value={settings.currencyCode} onChange={(event) => field("currencyCode", event.target.value)}>{["USD", "EUR", "GBP", "INR", "AUD", "CAD"].map((currency) => <option key={currency}>{currency}</option>)}</select></label><label>Timezone<input value={settings.timezone} onChange={(event) => field("timezone", event.target.value)} maxLength="80" required/></label><label>Date format<select value={settings.dateFormat} onChange={(event) => field("dateFormat", event.target.value)}><option>YYYY-MM-DD</option><option>DD/MM/YYYY</option><option>MM/DD/YYYY</option></select></label><button className="primary-button" disabled={busy}>Save preferences</button></div></form><form className="analytics-card settings-form" onSubmit={savePassword}><div className="analytics-card-heading"><div><span className="eyebrow">Security</span><h2>Change password</h2></div></div><div className="settings-fields"><label>Current password<input type="password" value={passwords.currentPassword} onChange={(event) => setPasswords({ ...passwords, currentPassword: event.target.value })} required/></label><label>New password<input type="password" value={passwords.newPassword} onChange={(event) => setPasswords({ ...passwords, newPassword: event.target.value })} minLength="8" maxLength="128" required/></label><button className="primary-button" disabled={busy}>Update password</button></div></form></div>}<footer className="page-footer"><span>ALPHA / SETTINGS</span><span>Tenant-scoped preferences</span></footer></div>;
}
