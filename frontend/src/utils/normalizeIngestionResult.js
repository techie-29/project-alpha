export function normalizeIngestionResult(response, selectedFile) {
  const data = response?.data || {};
  const sourceFile = data.sourceFile || {};
  const dataset = data.dataset || {};
  const profile = dataset.profile || {};

  const rows = Array.isArray(dataset.rows) ? dataset.rows : [];
  const profileColumns = Array.isArray(profile.columns) ? profile.columns : [];
  const headers = Array.isArray(dataset.headers)
    ? dataset.headers
    : profileColumns.map((column) => column.name);

  const profilesByName = new Map(
    profileColumns.map((column) => [column.name, column])
  );

  const columns = headers.map((name) => {
    const columnProfile = profilesByName.get(name);

    return {
      name,
      detectedType: columnProfile?.detectedType || "unknown",
    };
  });

  const fallbackFormat = selectedFile?.name
    .split(".")
    .pop()
    ?.toUpperCase();

  return {
    fileName: sourceFile.fileName || selectedFile?.name || "Uploaded dataset",
    fileType: sourceFile.format?.toUpperCase() || fallbackFormat || "Unknown",
    sizeBytes: sourceFile.sizeBytes ?? selectedFile?.size ?? null,
    rowCount: profile.rowCount ?? rows.length,
    columnCount: profile.columnCount ?? headers.length,
    sheetName: sourceFile.sheetName || null,
    datasetType: dataset.type?.type || "unknown",
    datasetTypeConfidence: dataset.type?.confidence ?? 0,
    skippedRowCount: data.processing?.skippedRowCount ?? 0,
    warnings: Array.isArray(data.processing?.warnings) ? data.processing.warnings : [],
    status:
      data.handoff?.status === "ready_for_mapping"
        ? "Ready for mapping"
        : "Ingested",
    rows,
    columns,
  };
}
