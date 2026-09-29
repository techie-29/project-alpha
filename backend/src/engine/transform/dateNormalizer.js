const MONTHS = {
  jan: 1, january: 1, feb: 2, february: 2, mar: 3, march: 3,
  apr: 4, april: 4, may: 5, jun: 6, june: 6, jul: 7, july: 7,
  aug: 8, august: 8, sep: 9, sept: 9, september: 9, oct: 10,
  october: 10, nov: 11, november: 11, dec: 12, december: 12
};

function isoDate(year, month, day) {
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) return null;
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function fullYear(value) {
  const year = Number(value);
  return year < 100 ? 2000 + year : year;
}

function detectDateOrder(values) {
  let sawDmy = false;
  let sawMdy = false;
  let sawAmbiguous = false;

  values.forEach((value) => {
    const match = String(value ?? "").trim().match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})$/);
    if (!match) return;
    const first = Number(match[1]);
    const second = Number(match[2]);
    if (first > 12 && second <= 12) sawDmy = true;
    else if (second > 12 && first <= 12) sawMdy = true;
    else if (first <= 12 && second <= 12) sawAmbiguous = true;
  });

  if (sawDmy && sawMdy) return { order: null, reason: "conflicting_evidence" };
  if (sawDmy) return { order: "DMY", reason: "day_above_12" };
  if (sawMdy) return { order: "MDY", reason: "month_above_12" };
  if (sawAmbiguous) return { order: null, reason: "ambiguous" };
  return { order: null, reason: "not_needed" };
}

function parseDate(value, order = null) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  const text = String(value ?? "").trim();
  if (!text) return null;

  let match = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
  if (match) return isoDate(Number(match[1]), Number(match[2]), Number(match[3]));

  match = text.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})$/);
  if (match) {
    if (!order) return null;
    const first = Number(match[1]);
    const second = Number(match[2]);
    const year = fullYear(match[3]);
    return order === "DMY"
      ? isoDate(year, second, first)
      : isoDate(year, first, second);
  }

  match = text.match(/^(\d{1,2})\s+([a-z]+)\s*,?\s*(\d{2,4})$/i) ||
    text.match(/^([a-z]+)\s+(\d{1,2})\s*,?\s*(\d{2,4})$/i);
  if (match) {
    const monthFirst = Number.isNaN(Number(match[1]));
    const month = MONTHS[String(monthFirst ? match[1] : match[2]).toLowerCase()];
    const day = Number(monthFirst ? match[2] : match[1]);
    return month ? isoDate(fullYear(match[3]), month, day) : null;
  }

  return null;
}

module.exports = { detectDateOrder, parseDate, isoDate };
