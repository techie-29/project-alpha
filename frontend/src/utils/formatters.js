export function formatNumber(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, ...options }).format(Number(value));
}

export function formatMoney(value) {
  return formatNumber(value, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined) return "—";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function titleCase(value = "") {
  return String(value).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
