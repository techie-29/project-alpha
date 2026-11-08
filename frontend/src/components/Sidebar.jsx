import { NavLink } from "react-router-dom";
import { useAnalysis } from "../context/AnalysisContext";

// Every item is a real page. 'section' items live inside the current analysis (/analysis/:id/<section>).
export const NAV = [
  { group: null, items: [{ label: "Overview", icon: "home", section: "overview" }] },
  { group: "Data", items: [
    { label: "Upload", icon: "upload", to: "/upload" },
    { label: "Header Mapping", icon: "map", section: "mapping" },
    { label: "Data Quality", icon: "shield", section: "quality" },
    { label: "Data Dictionary", icon: "book", section: "dictionary" },
    { label: "Data Explorer", icon: "table", section: "explorer" }] },
  { group: "Analysis", items: [
    { label: "Sales", icon: "chart", section: "sales" },
    { label: "Customers", icon: "users", section: "customers" },
    { label: "Products", icon: "box", section: "products" },
    { label: "Trends", icon: "trend", section: "trends" }] },
  { group: "Insights", items: [
    { label: "Suggestions", icon: "spark", section: "suggestions" },
    { label: "Alerts", icon: "bell", section: "alerts" }] },
  { group: "Tools", items: [
    { label: "What-If", icon: "sliders", section: "whatif" },
    { label: "Ask Your Data", icon: "chat", section: "ask" },
    { label: "Under the Hood", icon: "cog", section: "hood" }] },
];

export function NavIcon({ name }) {
  const paths = {
    home: <><path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/></>,
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></>,
    map: <><path d="M4 6h6M4 12h6M4 18h6"/><path d="M14 6h6M14 12h6M14 18h6"/><path d="m10 6 4 6-4 6"/></>,
    shield: <><path d="M12 3 5 6v6c0 4.4 3 7.6 7 9 4-1.4 7-4.6 7-9V6l-7-3Z"/><path d="m9 12 2 2 4-4"/></>,
    book: <><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z"/><path d="M4 19a2 2 0 0 1 2-2h13M8 7h7"/></>,
    table: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/></>,
    chart: <><path d="M4 19V10"/><path d="M10 19V5"/><path d="M16 19v-7"/><path d="M22 19H2"/></>,
    users: <><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14.7c1.9.7 3.1 2.5 3.5 5.3"/></>,
    box: <><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
    trend: <><path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/></>,
    spark: <><path d="m12 3 1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7L12 3Z"/><path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z"/></>,
    bell: <><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10.3 21a2 2 0 0 0 3.4 0"/></>,
    sliders: <><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></>,
    chat: <><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.6A8 8 0 1 1 21 12Z"/></>,
    cog: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></>,
    list: <><path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H3v-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

export default function Sidebar({ open, onNavigate }) {
  const { currentId, status } = useAnalysis() || {};
  const ready = currentId && status?.status === "done";
  const link = (it) => {
    if (it.to) return <NavLink className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`} to={it.to} onClick={onNavigate}><NavIcon name={it.icon}/><span>{it.label}</span></NavLink>;
    if (!currentId) return <span className="nav-item is-off" title="Run an analysis first"><NavIcon name={it.icon}/><span>{it.label}</span></span>;
    return <NavLink className={({ isActive }) => `nav-item ${isActive ? "active" : ""} ${ready ? "" : "is-wait"}`} to={`/analysis/${currentId}/${it.section}`} onClick={onNavigate}><NavIcon name={it.icon}/><span>{it.label}</span></NavLink>;
  };
  return <aside className={`sidebar ${open ? "is-open" : ""}`}>
    <div className="brand"><div className="brand-mark">A</div><div><strong>Alpha</strong><span>Business Intelligence</span></div></div>
    <nav aria-label="Primary navigation">
      {NAV.map((g, i) => <div key={i} className="nav-group">{g.group && <p className="nav-label">{g.group}</p>}<ul>{g.items.map((it) => <li key={it.label}>{link(it)}</li>)}</ul></div>)}
    </nav>
    <div className="sidebar-footer">
      <NavLink className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`} to="/analyses" onClick={onNavigate}><NavIcon name="list"/><span>All analyses</span></NavLink>
      <NavLink className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`} to="/settings" onClick={onNavigate}><NavIcon name="settings"/><span>Settings</span></NavLink>
    </div>
  </aside>;
}
