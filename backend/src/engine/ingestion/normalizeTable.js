function isEmpty(value) {
  return value === null || value === undefined || String(value).trim() === "";
}

function countValues(row) {
  return row.filter((value) => !isEmpty(value)).length;
}

function getRowWidth(row) {
  let lastValueIndex = -1;
  for (let index = 0; index < row.length; index += 1) {
    if (!isEmpty(row[index])) lastValueIndex = index;
  }
  return lastValueIndex + 1;
}

function findHeaderRow(rawRows) {
  for (let index = 0; index < rawRows.length; index += 1) {
    const row = rawRows[index];
    if (countValues(row) < 2) continue;

    const width = getRowWidth(row);
    const possibleHeaders = row.slice(0, width);
    if (possibleHeaders.some(isEmpty)) continue;

    let nextRow = null;
    for (let next = index + 1; next < rawRows.length; next += 1) {
      if (countValues(rawRows[next]) > 0) {
        nextRow = rawRows[next];
        break;
      }
    }

    if (!nextRow || getRowWidth(nextRow) > width) continue;
    return index;
  }
  return -1;
}

function makeUniqueHeaders(rawHeaders) {
  const counts = new Map();

  return rawHeaders.map((header) => {
    const base = String(header).trim();
    if (!base) throw new Error("Dataset contains an empty header");

    const key = base.toLowerCase();
    const count = (counts.get(key) || 0) + 1;
    counts.set(key, count);

    return count === 1 ? base : `${base}_${count}`;
  });
}

function normalizeTable(rawRows) {
  if (!Array.isArray(rawRows) || rawRows.length === 0) {
    throw new Error("Dataset is empty");
  }

  const headerIndex = findHeaderRow(rawRows);
  if (headerIndex === -1) throw new Error("No usable table could be found");

  const width = getRowWidth(rawRows[headerIndex]);
  const headers = makeUniqueHeaders(rawRows[headerIndex].slice(0, width));
  const rows = [];
  const skippedRows = [];

  for (let index = headerIndex + 1; index < rawRows.length; index += 1) {
    const rawRow = rawRows[index];
    if (countValues(rawRow) === 0) continue;

    const hasExtraValues = rawRow.slice(width).some((value) => !isEmpty(value));
    if (hasExtraValues) {
      skippedRows.push({ sourceRowNumber: index + 1, reason: "extra_values" });
      continue;
    }

    const row = {};
    headers.forEach((header, columnIndex) => {
      const value = rawRow[columnIndex];
      row[header] = isEmpty(value) ? null : value;
    });

    rows.push(row);
  }

  if (rows.length === 0) throw new Error("Dataset contains headers but no data rows");

  return { headers, rows, headerRowNumber: headerIndex + 1, skippedRows };
}

module.exports = {
  isEmpty,
  findHeaderRow,
  makeUniqueHeaders,
  normalizeTable
};
