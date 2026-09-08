import { useEffect, useState } from "react";
import {
  getAdminDashboard,
  getAdminUsers,
  getAdminDatasets,
  getAdminSystem,
  setBusinessStatus,
  deleteBusiness,
  getBusinessDatasets,
  getDatasetDetails,
  deleteDataset,
} from "../services/adminApi";
import "./AdminPanel.css";

const sections = ["Overview", "Businesses", "Datasets", "System"];

export default function AdminPanel({ token, account, onLogout }) {
  const [section, setSection] = useState("Overview");
  const [dashboard, setDashboard] = useState(null);
  const [users, setUsers] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [system, setSystem] = useState(null);
  const [selectedBusiness, setSelectedBusiness] = useState(null);
  const [businessDatasets, setBusinessDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [previewRows, setPreviewRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function refreshAdminData() {
    setLoading(true);
    setError("");
    const results = await Promise.allSettled([
      getAdminDashboard(token),
      getAdminUsers(token),
      getAdminDatasets(token),
      getAdminSystem(token),
    ]);

    const [d, u, ds, s] = results;
    const errors = [];
    if (d.status === "fulfilled") setDashboard(d.value.data); else errors.push(`Overview: ${d.reason.message}`);
    if (u.status === "fulfilled") setUsers(u.value.data.users || []); else errors.push(`Businesses: ${u.reason.message}`);
    if (ds.status === "fulfilled") setDatasets(ds.value.data.datasets || []); else errors.push(`Datasets: ${ds.reason.message}`);
    if (s.status === "fulfilled") setSystem(s.value.data); else errors.push(`System: ${s.reason.message}`);
    setError(errors.join(" | "));
    setLoading(false);
  }

  useEffect(() => { refreshAdminData(); }, [token]);

  async function handleStatusChange(user) {
    const nextStatus = user.accountStatus === "disabled" ? "active" : "disabled";
    if (!window.confirm(`${nextStatus === "disabled" ? "Disable" : "Enable"} ${user.businessName}?`)) return;
    setWorking(true); setError(""); setMessage("");
    try {
      await setBusinessStatus(token, user.id, nextStatus);
      setMessage(`${user.businessName} is now ${nextStatus}. This change applies across protected Project Alpha routes.`);
      await refreshAdminData();
    } catch (e) { setError(e.message); }
    finally { setWorking(false); }
  }

  async function handleDeleteBusiness(user) {
    if (!window.confirm(`Delete ${user.businessName}? This also deletes all of its ingestions and stored rows.`)) return;
    setWorking(true); setError(""); setMessage("");
    try {
      await deleteBusiness(token, user.id);
      if (selectedBusiness?.id === user.id) { setSelectedBusiness(null); setBusinessDatasets([]); }
      setMessage(`${user.businessName} and its related ingestion data were deleted.`);
      await refreshAdminData();
    } catch (e) { setError(e.message); }
    finally { setWorking(false); }
  }

  async function handleViewBusiness(user) {
    setSelectedBusiness(user); setSelectedDataset(null); setError("");
    try {
      const response = await getBusinessDatasets(token, user.id);
      setBusinessDatasets(response.data.datasets || []);
    } catch (e) { setError(e.message); }
  }

  async function handleViewDataset(dataset) {
    setError(""); setMessage("");
    try {
      const response = await getDatasetDetails(token, dataset.id);
      setSelectedDataset(response.data.dataset);
      setPreviewRows(response.data.previewRows || []);
    } catch (e) { setError(e.message); }
  }

  async function handleDeleteDataset(dataset) {
    if (!window.confirm(`Delete ${dataset.fileName}? Its persisted ingestion rows will also be removed.`)) return;
    setWorking(true); setError(""); setMessage("");
    try {
      await deleteDataset(token, dataset.id);
      if (selectedDataset?.id === dataset.id) { setSelectedDataset(null); setPreviewRows([]); }
      setMessage(`${dataset.fileName} was deleted from Project Alpha.`);
      await refreshAdminData();
      if (selectedBusiness) {
        const response = await getBusinessDatasets(token, selectedBusiness.id);
        setBusinessDatasets(response.data.datasets || []);
      }
    } catch (e) { setError(e.message); }
    finally { setWorking(false); }
  }

  const stats = dashboard?.stats || {};
  const formatDate = (value) => value ? new Date(value).toLocaleString() : "—";
  const number = (value) => Number(value || 0).toLocaleString();

  return <div className="admin-shell">
    <aside className="admin-sidebar">
      <div className="admin-brand"><div className="admin-mark">A</div><div><strong>Alpha</strong><span>Administration</span></div></div>
      <p className="admin-nav-label">Control center</p>
      <nav>{sections.map((item) => <button key={item} className={section === item ? "admin-nav active" : "admin-nav"} onClick={() => setSection(item)}>{item}</button>)}</nav>
      <div className="future-nav"><span>UPCOMING</span><p>Validation controls</p><p>Analytics oversight</p><p>Reports & exports</p></div>
      <div className="admin-side-status"><i/>Modules 01 + 02 controlled here</div>
    </aside>

    <main className="admin-main">
      <header className="admin-topbar"><div><span className="admin-kicker">PROJECT ALPHA</span><strong>Admin Control Center</strong></div><div className="admin-account"><div className="admin-avatar">{(account?.businessName || "AD").slice(0,2).toUpperCase()}</div><div><strong>{account?.businessName || account?.email || "Administrator"}</strong><span>Administrator</span></div><button onClick={onLogout}>Sign out</button></div></header>
      <div className="admin-content">
        {loading && <div className="admin-notice">Loading live Project Alpha data...</div>}
        {message && <div className="admin-success">{message}</div>}
        {error && <div className="admin-error">{error}</div>}

        {section === "Overview" && <>
          <div className="admin-heading"><div><span>Application control</span><h1>Project Alpha administration</h1><p>Monitor the application and manage the same accounts and datasets used by the business-facing experience.</p></div><div className="live-pill"><i/>Database backed</div></div>
          <div className="stat-grid">
            <Stat label="Business accounts" value={number(stats.businessAccounts)} detail={`${number(stats.disabledAccounts)} disabled`} />
            <Stat label="Datasets uploaded" value={number(stats.totalUploads)} detail="Module 02 ingestions" />
            <Stat label="Rows stored" value={number(stats.totalRows)} detail="Actual persisted rows" />
            <Stat label="Pipeline stage" value="2 / 8" detail="Controls expand with modules" />
          </div>
          <div className="admin-grid">
            <section className="admin-card wide"><CardTitle title="Recent ingestion activity" note="Live data across all business accounts"/><Table headers={["Dataset","Business","Shape","Status","Uploaded","Control"]} rows={(dashboard?.recentUploads || []).map(x => [x.fileName,x.businessName,`${number(x.rowCount)} × ${number(x.columnCount)}`,x.status,formatDate(x.createdAt),<button className="admin-action" onClick={() => { setSection("Datasets"); handleViewDataset(x); }}>Open</button>])}/></section>
            <section className="admin-card"><CardTitle title="Project roadmap" note="Secondary status view"/><div className="roadmap">{(system?.modules || []).map(m => <div key={m.id} className={`roadmap-item ${m.status}`}><b>{String(m.id).padStart(2,"0")}</b><div><strong>{m.name}</strong><span>{m.status === "completed" ? "Operational" : "Upcoming"}</span></div></div>)}</div></section>
          </div>
        </>}

        {section === "Businesses" && <>
          <PageTitle title="Business Management" text="Enable, disable, inspect, or remove accounts. Changes affect authentication and protected application routes."/>
          <section className="admin-card"><Table headers={["Business","Email","Status","Uploads","Created","Controls"]} rows={users.filter(x => x.role !== "admin").map(x => [x.businessName,x.email,<Status value={x.accountStatus}/>,number(x.uploadCount),formatDate(x.createdAt),<div className="admin-actions"><button className="admin-action" onClick={() => handleViewBusiness(x)}>View</button><button className="admin-action" disabled={working} onClick={() => handleStatusChange(x)}>{x.accountStatus === "disabled" ? "Enable" : "Disable"}</button><button className="admin-action danger" disabled={working} onClick={() => handleDeleteBusiness(x)}>Delete</button></div>])}/></section>
          {selectedBusiness && <section className="admin-card control-detail"><CardTitle title={selectedBusiness.businessName} note={`${selectedBusiness.email} · ${selectedBusiness.accountStatus}`}/><Table headers={["Dataset","Format","Rows","Columns","Status","Uploaded","Control"]} rows={businessDatasets.map(x => [x.fileName,x.fileFormat,number(x.rowCount),number(x.columnCount),x.status,formatDate(x.createdAt),<button className="admin-action" onClick={() => { setSection("Datasets"); handleViewDataset(x); }}>Open</button>])}/></section>}
        </>}

        {section === "Datasets" && <>
          <PageTitle title="Dataset Management" text="Inspect or delete persisted Module 02 datasets. Deleting an ingestion also removes its stored rows through the database relationship."/>
          <section className="admin-card"><Table headers={["Dataset","Business","Format","Rows","Columns","Status","Uploaded","Controls"]} rows={datasets.map(x => [x.fileName,x.businessName,x.fileFormat,number(x.rowCount),number(x.columnCount),x.status,formatDate(x.createdAt),<div className="admin-actions"><button className="admin-action" onClick={() => handleViewDataset(x)}>Preview</button><button className="admin-action danger" disabled={working} onClick={() => handleDeleteDataset(x)}>Delete</button></div>])}/></section>
          {selectedDataset && <DatasetDetail dataset={selectedDataset} rows={previewRows} number={number} formatDate={formatDate} onDelete={() => handleDeleteDataset(selectedDataset)}/>} 
        </>}

        {section === "System" && <><PageTitle title="System & Roadmap" text="Runtime health and the extension points for future administrative controls."/><div className="system-grid"><section className="admin-card"><CardTitle title="Runtime" note="Current environment"/><Info label="Backend" value={system?.backend}/><Info label="Database" value={system?.database}/><Info label="Accepted files" value={system?.supportedFormats?.join(", ")}/><Info label="Upload limit" value={`${system?.maximumUploadMb || 10} MB`}/></section><section className="admin-card"><CardTitle title="Module readiness" note="New controls attach here as modules are completed"/><div className="roadmap">{(system?.modules || []).map(m => <div key={m.id} className={`roadmap-item ${m.status}`}><b>{String(m.id).padStart(2,"0")}</b><div><strong>{m.name}</strong><span>{m.status}</span></div></div>)}</div></section></div></>}
      </div>
    </main>
  </div>;
}

function DatasetDetail({ dataset, rows, number, formatDate, onDelete }) {
  return <section className="admin-card control-detail">
    <CardTitle title={dataset.fileName} note={`${dataset.businessName || "Unknown business"} · ${dataset.fileFormat}`}/>
    <div className="detail-grid"><Info label="Rows" value={number(dataset.rowCount)}/><Info label="Columns" value={number(dataset.columnCount)}/><Info label="Status" value={dataset.status}/><Info label="Uploaded" value={formatDate(dataset.createdAt)}/></div>
    <div className="detail-toolbar"><strong>First 25 persisted rows</strong><button className="admin-action danger" onClick={onDelete}>Delete dataset</button></div>
    <div className="preview-json">{rows.length ? rows.map((row) => <div key={row.rowNumber}><b>#{row.rowNumber}</b><pre>{JSON.stringify(typeof row.rawData === "string" ? JSON.parse(row.rawData) : row.rawData, null, 2)}</pre></div>) : <p>No stored rows found.</p>}</div>
  </section>;
}

function Status({value}) { return <span className={`status-badge ${value}`}>{value || "active"}</span>; }
function Stat({label,value,detail}) { return <div className="stat-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>; }
function CardTitle({title,note}) { return <div className="card-title"><div><h2>{title}</h2><p>{note}</p></div></div>; }
function PageTitle({title,text}) { return <div className="admin-heading compact"><div><span>Administration</span><h1>{title}</h1><p>{text}</p></div></div>; }
function Info({label,value}) { return <div className="info-row"><span>{label}</span><strong>{value || "—"}</strong></div>; }
function Table({headers,rows}) { return <div className="admin-table-wrap"><table className="admin-table"><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.length ? rows.map((r,i)=><tr key={i}>{r.map((c,j)=><td key={j}>{c ?? "—"}</td>)}</tr>) : <tr><td colSpan={headers.length} className="empty-cell">No persisted records found.</td></tr>}</tbody></table></div>; }
