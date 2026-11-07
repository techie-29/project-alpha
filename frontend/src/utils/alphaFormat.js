export function compact(v) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "—";
  const x = Number(v), a = Math.abs(x);
  if (a >= 1e9) return `${(x / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${(x / 1e6).toFixed(2)}M`;
  if (a >= 1e4) return `${(x / 1e3).toFixed(1)}K`;
  if (a >= 100) return Math.round(x).toLocaleString();
  return x.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/** Same rules as the engine's fmt_value, so numbers read the same everywhere. */
export function fmtValue(v, fmt = "number", unit = "") {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "—";
  const x = Number(v);
  if (fmt === "pct") return `${(x * 100).toFixed(1)}%`;
  if (fmt === "rating") return x.toFixed(2);
  if (fmt === "days") return `${x.toFixed(1)} ${["min", "hours", "days"].includes(unit) ? unit : "days"}`;
  if (fmt === "count") return compact(Math.round(x));
  const s = compact(x);
  return fmt === "money" && unit ? `${unit} ${s}` : s;
}

export function axisFmt(fmt) {
  return (v) => (fmt === "pct" ? `${Math.round(v * 100)}%` : compact(v));
}

export function signedPct(v, digits = 1) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "—";
  const x = Number(v) * 100;
  return `${x > 0 ? "+" : ""}${x.toFixed(digits)}%`;
}

export function change(v, fmt) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return null;
  return fmt === "pct" ? `${v > 0 ? "+" : ""}${(v * 100).toFixed(1)} pts` : signedPct(v);
}

export function fileSize(bytes) {
  const b = Number(bytes) || 0;
  if (b >= 1048576) return `${(b / 1048576).toFixed(1)} MB`;
  if (b >= 1024) return `${Math.round(b / 1024)} KB`;
  return `${b} B`;
}

export function cellText(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T00:00:00/.test(value)) return value.slice(0, 10);
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
  return String(value);
}

export const TYPE_LABELS = { measure: "Number", category: "Group", id: "Identifier", time: "Date", flag: "Yes / no", text: "Text", ignore: "Ignore" };
export const ROLE_TEXT = { transactions: "Activity log", lines: "Line items", master: "Master list", snapshot: "Snapshot over time", periodic: "Period totals", reference: "Reference table", summary: "Summary (not analysed)" };
export const CLAIM_CLASS = { Calculated: "calc", "Supported by evidence": "supported", "Possible (early sign)": "early" };

export function buildConfirmations({ concepts = {}, links = {}, types = {}, rowOrder = {}, dateOrder = {}, timeCol = {}, modes = {}, rename = {}, fixes = {}, mapped = {} }) {
  const out = { concepts, links, columns: types, rows_in_time_order: rowOrder };
  if (Object.keys(dateOrder).length) out.date_order = dateOrder;     // { file: { column: "day-first" | "month-first" } }
  if (Object.keys(timeCol).length) out.time_col = timeCol;           // { file: column used as the timeline }
  const keep = Object.fromEntries(Object.entries(modes).filter(([, m]) => m === "keep").map(([k]) => [k, true]));
  if (Object.keys(keep).length) out.keep = keep;                     // { "file::column": true }: a plain column, no special business meaning
  const names = Object.fromEntries(Object.entries(rename).filter(([k, v]) => modes[k] === "custom" && String(v || "").trim()).map(([k, v]) => [k, String(v).trim()]));
  if (Object.keys(names).length) out.rename = names;                 // { "file::column": "New name" }
  if (Object.keys(fixes).length) out.fixes = fixes;                  // { file: { problemKind: choice } }
  if (Object.keys(mapped).length) out.mapped = mapped;               // { "file::column": concept } as shown on the mapping screen
  return out;
}

/** What each column was read as, as shown to the owner (their change wins), keyed "file::original column". 'Keep it' means a plain column. */
export function mappedConcepts(reading, { concepts = {}, modes = {} } = {}) {
  const out = {};
  for (const f of reading?.files || []) {
    for (const c of f.columns || []) {
      const key = `${f.name}::${c.original || c.name}`;
      const keep = modes[key] === "keep";
      const concept = keep ? (c.type === "measure" ? "number" : c.type === "category" || c.type === "flag" ? "group" : null) : (concepts[key] || c.concept);
      if (concept) out[key] = concept;
    }
  }
  return out;
}

export function dateExample(order, example) {
  if (!example) return "";
  return example.replace("->", "→");
}
