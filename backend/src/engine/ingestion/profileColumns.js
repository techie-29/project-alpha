function isMissing(value) {
  return value === null || value === undefined ||
    (typeof value === "string" && value.trim() === "");
}

function isNumber(value) {
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value !== "string") return false;
  const cleaned = value.trim().replace(/,/g, "");
  return cleaned !== "" && Number.isFinite(Number(cleaned));
}

function isDate(value) {
  if (value instanceof Date) return !Number.isNaN(value.getTime());
  if (typeof value !== "string") return false;

  const text = value.trim();
  const yearFirst = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/;
  const dayFirst = /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/;
  let match = text.match(yearFirst);
  let year, month, day;

  if (match) {
    [, year, month, day] = match.map(Number);
  } else {
    match = text.match(dayFirst);
    if (!match) return false;
    day = Number(match[1]);
    month = Number(match[2]);
    year = Number(match[3]);
  }

  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day;
}

function detectValueType(value) {
  if (isNumber(value)) return "number";
  if (isDate(value)) return "date";
  return "text";
}

function profileColumns(dataset) {
  const columns = dataset.headers.map((name) => {
    const present = dataset.rows
      .map((row) => row[name])
      .filter((value) => !isMissing(value));

    const types = new Set(present.map(detectValueType));
    const detectedType = types.size === 0
      ? "unknown"
      : types.size === 1
        ? [...types][0]
        : "mixed";

    return {
      name,
      detectedType,
      missingCount: dataset.rows.length - present.length,
      nonMissingCount: present.length
    };
  });

  return {
    rowCount: dataset.rows.length,
    columnCount: dataset.headers.length,
    columns
  };
}

module.exports = { profileColumns, isMissing, isNumber, isDate };
