function firstArray(...candidates) {
  return candidates.find(Array.isArray) || [];
}

function valueFrom(...candidates) {
  return candidates.find((value) => value !== undefined && value !== null && value !== "");
}

export function normalizeIngestionResult(response, selectedFile) {
  const nested = response.result || response.dataset || response.ingestion || {};
  const rows = firstArray(
    response.data,
    response.rows,
    response.preview,
    response.sampleRows,
    nested.data,
    nested.rows,
    nested.preview
  );

  const rawColumns = firstArray(response.columns, response.headers, nested.columns, nested.headers);
  const profileColumns = firstArray(
    response.columnProfiles,
    response.columnProfile,
    response.profile?.columns,
    nested.columnProfiles
  );

  const columnObjects = rawColumns.filter((column) => column && typeof column === "object");
  const suppliedHeaders = rawColumns.map((column) =>
    typeof column === "string" ? column : column.name || column.columnName || column.header || column.key
  ).filter(Boolean);
  const headers = suppliedHeaders.length ? suppliedHeaders : rows[0] && typeof rows[0] === "object" ? Object.keys(rows[0]) : [];

  const profilesByName = new Map(
    [...columnObjects, ...profileColumns].map((profile) => [
      profile.name || profile.columnName || profile.header || profile.key,
      profile,
    ])
  );

  const columns = headers.map((name) => {
    const profile = profilesByName.get(name) || {};
    return {
      name,
      detectedType: valueFrom(profile.detectedType, profile.type, profile.dataType),
      missingCount: valueFrom(profile.missingCount, profile.missing, profile.nullCount),
    };
  });

  const fallbackType = selectedFile?.name.split(".").pop()?.toUpperCase();
  return {
    fileName: valueFrom(response.fileName, response.filename, response.file?.name, nested.fileName, selectedFile?.name),
    fileType: valueFrom(response.fileType, response.mimetype, response.file?.type, nested.fileType, fallbackType),
    rowCount: valueFrom(response.rowCount, response.totalRows, response.profile?.rowCount, nested.rowCount, rows.length),
    columnCount: valueFrom(response.columnCount, response.totalColumns, response.profile?.columnCount, nested.columnCount, headers.length),
    sheetName: valueFrom(response.sheetName, response.sheet, nested.sheetName),
    status: valueFrom(response.status, nested.status, response.success === false ? "Failed" : "Ingested"),
    rows,
    columns,
  };
}
