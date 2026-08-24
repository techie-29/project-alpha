const navItems = [
  { label: "Dashboard", icon: "grid", disabled: true },
  { label: "Upload", icon: "upload", active: true },
  { label: "Analytics", icon: "chart", disabled: true },
  { label: "Insights", icon: "spark", disabled: true },
  { label: "Settings", icon: "settings", disabled: true },
];

function NavIcon({ name }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></>,
    chart: <><path d="M4 19V10"/><path d="M10 19V5"/><path d="M16 19v-7"/><path d="M22 19H2"/></>,
    spark: <><path d="m12 3 1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7L12 3Z"/><path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H3v-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

export default function Sidebar() {
  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark">A</div><div><strong>Alpha</strong><span>Business Intelligence</span></div></div>
    <nav aria-label="Primary navigation"><p className="nav-label">Workspace</p><ul>{navItems.map((item) => <li key={item.label}><button className={`nav-item ${item.active ? "active" : ""}`} disabled={item.disabled} aria-current={item.active ? "page" : undefined}><NavIcon name={item.icon}/><span>{item.label}</span>{item.disabled && <small>Soon</small>}</button></li>)}</ul></nav>
    <div className="sidebar-footer"><span className="status-dot"/>System ready</div>
  </aside>;
}
