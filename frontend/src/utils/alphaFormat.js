export function num(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const v = Number(value), a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (a >= 1e4) return `${(v / 1e3).toFixed(1)}K`;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: a >= 100 ? 0 : digits }).format(v);
}

export function amount(value, unit) {
  const n = num(value);
  return n === "—" ? n : unit ? `${unit} ${n}` : n;
}

export function percent(value, digits = 0) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function signedPercent(value, digits = 0) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const v = Number(value) * 100;
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function fileSize(bytes) {
  const b = Number(bytes) || 0;
  if (b >= 1048576) return `${(b / 1048576).toFixed(1)} MB`;
  if (b >= 1024) return `${Math.round(b / 1024)} KB`;
  return `${b} B`;
}

export const ROLE_LABELS = {
  time: "Date / time", measure: "Number to add up or average", category: "Group (category)", flag: "Yes / no", id: "Identifier",
  text: "Free text", constant: "Same value everywhere", empty: "Empty", time_of_day: "Time of day", ignore: "Ignore this column"
};
export const CHOOSABLE_ROLES = ["time", "measure", "category", "flag", "id", "text", "ignore"];

export const LEVEL_TEXT = { confirmed: "Supported by evidence", early: "Possible (early sign)" };
export const POLARITY_TEXT = { good: "Helps", bad: "Hurts", neutral: "Neither good nor bad" };

export function cellText(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T00:00:00$/.test(value)) return value.slice(0, 10);
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value);
}

/** Build the confirmations object the server expects from the choices made on the review screen. */
export function buildConfirmations({ roles = {}, links = {}, timeCols = {}, rowOrder = {} }) {
  return { columns: roles, links, time_col: timeCols, rows_in_time_order: rowOrder };
}
