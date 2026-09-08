import { useEffect, useState } from "react";
import { getAdminDashboard, getAdminUsers, getAdminDatasets, getAdminSystem } from "../services/adminApi";
import "./AdminPanel.css";

const sections = ["Overview", "Users", "Datasets", "System"];

export default function AdminPanel({ token, account, onLogout }) {
  const [section, setSection] = useState("Overview");
  const [dashboard, setDashboard] = useState(null);
  const [users, setUsers] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [system, setSystem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadAdminData() {
      setLoading(true);
      setError("");

      const results = await Promise.allSettled([
        getAdminDashboard(token),
        getAdminUsers(token),
        getAdminDatasets(token),
        getAdminSystem(token),
      ]);

      if (!active) return;

      const [dashboardResult, usersResult, datasetsResult, systemResult] = results;
      const errors = [];

      if (dashboardResult.status === "fulfilled") setDashboard(dashboardResult.value.data);
      else errors.push(`Overview: ${dashboardResult.reason.message}`);

      if (usersResult.status === "fulfilled") setUsers(usersResult.value.data.users || []);
      else errors.push(`Businesses: ${usersResult.reason.message}`);

      if (datasetsResult.status === "fulfilled") setDatasets(datasetsResult.value.data.datasets || []);
      else errors.push(`Datasets: ${datasetsResult.reason.message}`);

      if (systemResult.status === "fulfilled") setSystem(systemResult.value.data);
      else errors.push(`System: ${systemResult.reason.message}`);

      setError(errors.join(" | "));
      setLoading(false);
    }

    loadAdminData();
    return () => { active = false; };
  }, [token]);

  const stats = dashboard?.stats || {};
  const formatDate = (value) => value ? new Date(value).toLocaleString() : "—";
  const number = (value) => Number(value || 0).toLocaleString();

  return <div className="admin-shell">
    <aside className="admin-sidebar">
      <div className="admin-brand"><div className="admin-mark">A</div><div><strong>Alpha</strong><span>Administration</span></div></div>
      <p className="admin-nav-label">Control center</p>
      <nav>{sections.map((item) => <button key={item} className={section === item ? "admin-nav active" : "admin-nav"} onClick={() => setSection(item)}>{item}</button>)}</nav>
      <div className="future-nav"><span>UPCOMING</span><p>Validation monitoring</p><p>Analytics oversight</p><p>Reports & exports</p></div>
      <div className="admin-side-status"><i/>Modules 01 + 02 live</div>
    </aside>

    <main className="admin-main">
      <header className="admin-topbar"><div><span className="admin-kicker">PROJECT ALPHA</span><strong>Admin Control Center</strong></div><div className="admin-account"><div className="admin-avatar">{(account?.businessName || "AD").slice(0,2).toUpperCase()}</div><div><strong>{account?.businessName || account?.email || "Administrator"}</strong><span>Administrator</span></div><button onClick={onLogout}>Sign out</button></div></header>
      <div className="admin-content">
        {loading && <div className="admin-error">Loading live Project Alpha data from MySQL...</div>}
        {error && <div className="admin-error">Some admin information could not be loaded. {error}</div>}

        {section === "Overview" && <>
          <div className="admin-heading"><div><span>System overview</span><h1>Good to see you.</h1><p>Live information from the authentication and ingestion modules, with room for every upcoming Alpha module.</p></div><div className="live-pill"><i/>Database backed</div></div>
          <div className="stat-grid">
            <Stat label="Business accounts" value={number(stats.businessAccounts)} detail={`${number(stats.totalAccounts)} total accounts`} />
            <Stat label="Datasets uploaded" value={number(stats.totalUploads)} detail="Stored ingestion records" />
            <Stat label="Rows stored" value={number(stats.totalRows)} detail="Actual ingestion_rows records" />
            <Stat label="Pipeline stage" value="2 / 8" detail="6 modules upcoming" />
          </div>
          <div className="admin-grid">
            <section className="admin-card wide"><CardTitle title="Recent ingestion activity" note="Latest persisted datasets across all businesses"/><Table headers={["Dataset","Business","Shape","Status","Uploaded"]} rows={(dashboard?.recentUploads || []).map(x => [x.fileName,x.businessName,`${number(x.rowCount)} × ${number(x.columnCount)}`,x.status,formatDate(x.createdAt)])}/></section>
            <section className="admin-card"><CardTitle title="Project roadmap" note="Architecture stays open as Alpha grows"/><div className="roadmap">{(system?.modules || []).map(m => <div key={m.id} className={`roadmap-item ${m.status}`}><b>{String(m.id).padStart(2,"0")}</b><div><strong>{m.name}</strong><span>{m.status === "completed" ? "Operational" : "Upcoming"}</span></div></div>)}</div></section>
          </div>
        </>}

        {section === "Users" && <><PageTitle title="Business Accounts" text="Real accounts stored by Module 01 authentication."/><section className="admin-card"><Table headers={["Business","Email","Role","Uploads","Created"]} rows={users.map(x => [x.businessName,x.email,x.role,number(x.uploadCount),formatDate(x.createdAt)])}/></section></>}

        {section === "Datasets" && <><PageTitle title="Dataset Registry" text="Every persisted Module 02 ingestion, across all business accounts."/><section className="admin-card"><Table headers={["Dataset","Business","Format","Rows","Columns","Status","Uploaded"]} rows={datasets.map(x => [x.fileName,x.businessName,x.fileFormat,number(x.rowCount),number(x.columnCount),x.status,formatDate(x.createdAt)])}/></section></>}

        {section === "System" && <><PageTitle title="System & Roadmap" text="Current platform health and extension points reserved for upcoming modules."/><div className="system-grid"><section className="admin-card"><CardTitle title="Runtime" note="Current environment"/><Info label="Backend" value={system?.backend}/><Info label="Database" value={system?.database}/><Info label="Accepted files" value={system?.supportedFormats?.join(", ")}/><Info label="Upload limit" value={`${system?.maximumUploadMb || 10} MB`}/></section><section className="admin-card"><CardTitle title="Module readiness" note="Admin sections can be added as each module lands"/><div className="roadmap">{(system?.modules || []).map(m => <div key={m.id} className={`roadmap-item ${m.status}`}><b>{String(m.id).padStart(2,"0")}</b><div><strong>{m.name}</strong><span>{m.status}</span></div></div>)}</div></section></div></>}
      </div>
    </main>
  </div>;
}

function Stat({label,value,detail}) { return <div className="stat-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>; }
function CardTitle({title,note}) { return <div className="card-title"><div><h2>{title}</h2><p>{note}</p></div></div>; }
function PageTitle({title,text}) { return <div className="admin-heading compact"><div><span>Administration</span><h1>{title}</h1><p>{text}</p></div></div>; }
function Info({label,value}) { return <div className="info-row"><span>{label}</span><strong>{value || "—"}</strong></div>; }
function Table({headers,rows}) { return <div className="admin-table-wrap"><table className="admin-table"><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.length ? rows.map((r,i)=><tr key={i}>{r.map((c,j)=><td key={j}>{c ?? "—"}</td>)}</tr>) : <tr><td colSpan={headers.length} className="empty-cell">No persisted records found.</td></tr>}</tbody></table></div>; }
