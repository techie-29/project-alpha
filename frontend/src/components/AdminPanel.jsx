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
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getAdminDashboard(token), getAdminUsers(token), getAdminDatasets(token), getAdminSystem(token)])
      .then(([d, u, ds, s]) => {
        setDashboard(d.data); setUsers(u.data.users); setDatasets(ds.data.datasets); setSystem(s.data);
      })
      .catch((e) => setError(e.message));
  }, [token]);

  const stats = dashboard?.stats || {};
  const formatDate = (value) => value ? new Date(value).toLocaleString() : "—";

  return <div className="admin-shell">
    <aside className="admin-sidebar">
      <div className="admin-brand"><div className="admin-mark">A</div><div><strong>Alpha</strong><span>Administration</span></div></div>
      <p className="admin-nav-label">Control center</p>
      <nav>{sections.map((item) => <button key={item} className={section === item ? "admin-nav active" : "admin-nav"} onClick={() => setSection(item)}>{item}</button>)}</nav>
      <div className="future-nav"><span>UPCOMING</span><p>Validation monitoring</p><p>Analytics oversight</p><p>Reports & exports</p></div>
      <div className="admin-side-status"><i/>Modules 01 + 02 live</div>
    </aside>

    <main className="admin-main">
      <header className="admin-topbar"><div><span className="admin-kicker">PROJECT ALPHA</span><strong>Admin Control Center</strong></div><div className="admin-account"><div className="admin-avatar">{(account?.businessName || "AD").slice(0,2).toUpperCase()}</div><div><strong>{account?.businessName}</strong><span>Administrator</span></div><button onClick={onLogout}>Sign out</button></div></header>
      <div className="admin-content">
        {error && <div className="admin-error">{error}</div>}

        {section === "Overview" && <>
          <div className="admin-heading"><div><span>System overview</span><h1>Good to see you.</h1><p>Monitor the authentication and ingestion modules today, with room for every upcoming Alpha module.</p></div><div className="live-pill"><i/>Live system</div></div>
          <div className="stat-grid">
            <Stat label="Business accounts" value={stats.businessAccounts ?? "—"} detail="Module 01" />
            <Stat label="Datasets uploaded" value={stats.totalUploads ?? "—"} detail="Module 02" />
            <Stat label="Rows ingested" value={Number(stats.totalRows || 0).toLocaleString()} detail="Stored raw data" />
            <Stat label="Pipeline stage" value="2 / 8" detail="6 modules upcoming" />
          </div>
          <div className="admin-grid">
            <section className="admin-card wide"><CardTitle title="Recent ingestion activity" note="Latest datasets across all businesses"/><Table headers={["Dataset","Business","Shape","Status","Uploaded"]} rows={(dashboard?.recentUploads || []).map(x => [x.fileName,x.businessName,`${x.rowCount} × ${x.columnCount}`,x.status,formatDate(x.createdAt)])}/></section>
            <section className="admin-card"><CardTitle title="Project roadmap" note="Architecture stays open as Alpha grows"/><div className="roadmap">{(system?.modules || []).map(m => <div key={m.id} className={`roadmap-item ${m.status}`}><b>{String(m.id).padStart(2,"0")}</b><div><strong>{m.name}</strong><span>{m.status === "completed" ? "Operational" : "Upcoming"}</span></div></div>)}</div></section>
          </div>
        </>}

        {section === "Users" && <><PageTitle title="Business Accounts" text="Accounts created through Module 01 authentication."/><section className="admin-card"><Table headers={["Business","Email","Role","Uploads","Created"]} rows={users.map(x => [x.businessName,x.email,x.role,x.uploadCount,formatDate(x.createdAt)])}/></section></>}

        {section === "Datasets" && <><PageTitle title="Dataset Registry" text="Every ingestion stored by Module 02, across all business accounts."/><section className="admin-card"><Table headers={["Dataset","Business","Format","Rows","Columns","Status","Uploaded"]} rows={datasets.map(x => [x.fileName,x.businessName,x.fileFormat,x.rowCount,x.columnCount,x.status,formatDate(x.createdAt)])}/></section></>}

        {section === "System" && <><PageTitle title="System & Roadmap" text="Current platform health and the extension points reserved for upcoming modules."/><div className="system-grid"><section className="admin-card"><CardTitle title="Runtime" note="Current environment"/><Info label="Backend" value={system?.backend}/><Info label="Database" value={system?.database}/><Info label="Accepted files" value={system?.supportedFormats?.join(", ")}/><Info label="Upload limit" value={`${system?.maximumUploadMb || 10} MB`}/></section><section className="admin-card"><CardTitle title="Module readiness" note="Admin sections can be added as each module lands"/><div className="roadmap">{(system?.modules || []).map(m => <div key={m.id} className={`roadmap-item ${m.status}`}><b>{String(m.id).padStart(2,"0")}</b><div><strong>{m.name}</strong><span>{m.status}</span></div></div>)}</div></section></div></>}
      </div>
    </main>
  </div>;
}

function Stat({label,value,detail}) { return <div className="stat-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>; }
function CardTitle({title,note}) { return <div className="card-title"><div><h2>{title}</h2><p>{note}</p></div></div>; }
function PageTitle({title,text}) { return <div className="admin-heading compact"><div><span>Administration</span><h1>{title}</h1><p>{text}</p></div></div>; }
function Info({label,value}) { return <div className="info-row"><span>{label}</span><strong>{value || "—"}</strong></div>; }
function Table({headers,rows}) { return <div className="admin-table-wrap"><table className="admin-table"><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.length ? rows.map((r,i)=><tr key={i}>{r.map((c,j)=><td key={j}>{c ?? "—"}</td>)}</tr>) : <tr><td colSpan={headers.length} className="empty-cell">No records yet.</td></tr>}</tbody></table></div>; }
