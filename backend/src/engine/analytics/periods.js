function isoDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? new Date(value) : new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10);
}

function addDays(value, days) {
  const normalized = isoDate(value);
  if (!normalized) return null;
  const date = new Date(`${normalized}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function daysBetween(from, to) {
  const start = isoDate(from);
  const end = isoDate(to);
  if (!start || !end) return null;
  return Math.round((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000);
}

function periodForPreset(preset, anchor = new Date()) {
  const to = isoDate(anchor);
  if (!to) throw new Error("Invalid period anchor");
  const date = new Date(`${to}T00:00:00Z`);
  if (preset === "daily") return { from: to, to };
  if (preset === "weekly") return { from: addDays(to, -6), to };
  if (preset === "monthly") {
    return { from: `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}-01`, to };
  }
  if (preset === "quarterly") {
    const firstMonth = Math.floor(date.getUTCMonth() / 3) * 3;
    return { from: `${date.getUTCFullYear()}-${String(firstMonth + 1).padStart(2, "0")}-01`, to };
  }
  throw new Error(`Unsupported period preset: ${preset}`);
}

function normalizePeriod({ preset = "monthly", from, to, anchor = new Date() } = {}) {
  const period = preset === "custom"
    ? { from: isoDate(from), to: isoDate(to) }
    : periodForPreset(preset, anchor);
  if (!period.from || !period.to || period.from > period.to) {
    const error = new Error("A valid from/to date range is required");
    error.status = 400;
    error.code = "INVALID_PERIOD";
    throw error;
  }
  return period;
}

function previousPeriod(period) {
  const length = daysBetween(period.from, period.to) + 1;
  const to = addDays(period.from, -1);
  return { from: addDays(to, -(length - 1)), to };
}

function inPeriod(value, period) {
  const date = isoDate(value);
  return Boolean(date && date >= period.from && date <= period.to);
}

function filterByPeriod(records, period, field = "order_date") {
  return records.filter((record) => inPeriod(record[field], period));
}

module.exports = { isoDate, addDays, daysBetween, periodForPreset, normalizePeriod, previousPeriod, inPeriod, filterByPeriod };
