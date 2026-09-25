export const MAX_FILE_SIZE = 10 * 1024 * 1024;
export const MAX_BATCH_FILES = 10;
export const ALLOWED_EXTENSIONS = ["csv", "xlsx", "xls"];

export function validateFile(file) {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!extension || !ALLOWED_EXTENSIONS.includes(extension)) {
    return "Unsupported file type. Choose CSV, XLSX, or XLS.";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "File is larger than the 10 MB per-file limit.";
  }
  return "";
}

export function makeQueueItems(files, batchKey = Date.now()) {
  return files.slice(0, MAX_BATCH_FILES).map((file, index) => {
    const validationError = validateFile(file);
    return {
      id: `${batchKey}-${index}-${file.name}-${file.size}`,
      file,
      status: validationError ? "invalid" : "queued",
      progress: 0,
      error: validationError,
      response: null
    };
  });
}
