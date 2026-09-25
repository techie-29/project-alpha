import { useEffect, useMemo, useState } from "react";
import {
  confirmHeaderMapping,
  getHeaderMappingWorkspace
} from "../services/headerMappingApi";

const REASON_LABELS = {
  canonical_name: "Canonical name",
  alias: "Known alias",
  fuzzy: "Similar header",
  value_sniff_email: "Email values",
  duplicate_candidate: "Duplicate target",
  saved_template: "Saved template",
  saved_unmapped: "Saved as unmapped",
  confirmed: "Confirmed",
  unmapped: "No suggestion"
};

export default function HeaderMappingWorkspace({ ingestionId, token, onConfirmed }) {
  const [workspace, setWorkspace] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [saveTemplate, setSaveTemplate] = useState(true);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setStatus("loading");
    setError("");
    getHeaderMappingWorkspace(ingestionId, token).then((response) => {
      if (!active) return;
      setWorkspace(response.data);
      setMappings(response.data.mappings);
      setStatus(response.data.status === "ready_for_validation" ? "confirmed" : "editing");
      if (response.data.status === "ready_for_validation") onConfirmed?.(response.data);
    }).catch((requestError) => {
      if (!active) return;
      setError(requestError.message);
      setStatus("error");
    });
    return () => { active = false; };
  }, [ingestionId, token]);

  const selectedFields = useMemo(
    () => new Set(mappings.map((mapping) => mapping.field).filter(Boolean)),
    [mappings]
  );

  function updateMapping(originalHeader, field) {
    setMappings((items) => items.map((mapping) => (
      mapping.originalHeader === originalHeader
        ? { ...mapping, field: field || null, confidence: field ? 1 : 0, reason: "confirmed" }
        : mapping
    )));
  }

  async function handleConfirm() {
    setStatus("saving");
    setError("");
    try {
      const response = await confirmHeaderMapping(
        ingestionId,
        mappings.map(({ originalHeader, field }) => ({ originalHeader, field: field || null })),
        saveTemplate,
        token
      );
      setWorkspace(response.data);
      setMappings(response.data.mappings);
      setStatus("confirmed");
      onConfirmed?.(response.data);
    } catch (requestError) {
      setError(requestError.message);
      setStatus("editing");
    }
  }

  if (status === "loading") {
    return <section className="mapping-card mapping-loading"><span className="spinner"/>Loading mapping suggestions…</section>;
  }
  if (status === "error") {
    return <section className="mapping-card"><div className="error-banner"><span>!</span><div><strong>Mapping could not be loaded</strong><p>{error}</p></div></div></section>;
  }

  const mappedCount = mappings.filter((mapping) => mapping.field).length;
  const requiredGroups = workspace?.summary?.requiredFieldGroups || [];
  const coverage = requiredGroups.length > 0
    ? requiredGroups.filter((group) => group.some((field) => selectedFields.has(field))).length / requiredGroups.length
    : (mappings.length ? mappedCount / mappings.length : 0);
  const missing = requiredGroups
    .filter((group) => !group.some((field) => selectedFields.has(field)))
    .map((group) => group.join("|"));

  return <section className="mapping-card" aria-labelledby="mapping-title">
    <div className="mapping-header">
      <div><span className="eyebrow">Module 3</span><h2 id="mapping-title">Review header mapping</h2><p>Confirm Alpha&apos;s suggestions or choose a different canonical field.</p></div>
      <div className="mapping-score"><strong>{Math.round(coverage * 100)}%</strong><span>Required coverage</span></div>
    </div>

    {workspace.reusedSavedMapping && <div className="mapping-notice">A mapping saved for this exact header set was applied.</div>}
    {status === "confirmed" && <div className="mapping-confirmed">Mapping confirmed. This dataset is ready for validation.</div>}
    {error && <div className="error-banner"><span>!</span><div><strong>Mapping was not saved</strong><p>{error}</p></div></div>}

    <div className="mapping-stats">
      <div><span>Dataset type</span><strong>{workspace.datasetType}</strong></div>
      <div><span>Mapped</span><strong>{mappedCount}/{mappings.length}</strong></div>
      <div><span>Missing critical</span><strong>{missing.length}</strong></div>
    </div>

    {missing.length > 0 && <div className="missing-fields"><strong>Needed for full {workspace.datasetType} processing:</strong> {missing.join(", ")}</div>}

    <div className="mapping-table-wrapper">
      <table className="mapping-table">
        <thead><tr><th>Uploaded header</th><th>Canonical field</th><th>Confidence</th><th>Reason</th></tr></thead>
        <tbody>{mappings.map((mapping) => <tr key={mapping.originalHeader}>
          <td><code>{mapping.originalHeader}</code></td>
          <td><select
            value={mapping.field || ""}
            onChange={(event) => updateMapping(mapping.originalHeader, event.target.value)}
            disabled={status === "saving" || status === "confirmed"}
            aria-label={`Map ${mapping.originalHeader}`}
          >
            <option value="">Leave unmapped</option>
            {workspace.canonicalFields.map((field) => <option
              value={field}
              key={field}
              disabled={selectedFields.has(field) && mapping.field !== field}
            >{field}</option>)}
          </select></td>
          <td><span className="confidence-value">{mapping.field ? `${Math.round((mapping.confidence || 0) * 100)}%` : "—"}</span></td>
          <td>{REASON_LABELS[mapping.reason] || mapping.reason}</td>
        </tr>)}</tbody>
      </table>
    </div>

    {status !== "confirmed" && <div className="mapping-actions">
      <label><input type="checkbox" checked={saveTemplate} onChange={(event) => setSaveTemplate(event.target.checked)}/> Reuse this mapping for the same headers</label>
      <button className="primary-button" type="button" onClick={handleConfirm} disabled={status === "saving"}>
        {status === "saving" ? <><span className="spinner"/>Saving mapping…</> : "Confirm mapping"}
      </button>
    </div>}
  </section>;
}
