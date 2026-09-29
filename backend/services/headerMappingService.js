const crypto = require("node:crypto");
const { CANONICAL_FIELDS, normalizeHeader } = require("../src/engine/mapping/canonicalFields");
const { suggestMappings } = require("../src/engine/mapping/suggestMapping");
const { calculateMappingCoverage } = require("../src/engine/mapping/mappingCoverage");
const defaultRepository = require("./headerMappingPersistenceService");

function parseJson(value, fallback) {
  if (value === null || value === undefined) return fallback;
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function createHeaderSignature(headers) {
  const stableHeaders = headers.map(normalizeHeader).sort();
  return crypto.createHash("sha256").update(JSON.stringify(stableHeaders)).digest("hex");
}

function summarize({ datasetType, mappings, totalHeaders }) {
  const coverage = calculateMappingCoverage({ datasetType, mappings, totalHeaders });
  return {
    ...coverage,
    unmappedHeaders: totalHeaders - coverage.mappedHeaders
  };
}

function applySavedTemplate(suggestions, savedMappings) {
  const savedByHeader = new Map(
    savedMappings.map((mapping) => [mapping.originalHeader, mapping.field || null])
  );
  return suggestions.map((suggestion) => {
    if (!savedByHeader.has(suggestion.originalHeader)) return suggestion;
    const field = savedByHeader.get(suggestion.originalHeader);
    return {
      ...suggestion,
      field,
      confidence: field ? 1 : 0,
      reason: field ? "saved_template" : "saved_unmapped"
    };
  });
}

function validateMappings(headers, mappings) {
  if (!Array.isArray(mappings)) {
    const error = new Error("Mappings must be an array");
    error.status = 400;
    error.code = "INVALID_MAPPING";
    throw error;
  }

  const headerSet = new Set(headers);
  const seenHeaders = new Set();
  const seenFields = new Set();
  const normalized = mappings.map((mapping) => {
    const originalHeader = mapping?.originalHeader;
    const field = mapping?.field || null;

    if (!headerSet.has(originalHeader) || seenHeaders.has(originalHeader)) {
      const error = new Error(`Invalid or duplicate source header: ${originalHeader || "unknown"}`);
      error.status = 400;
      error.code = "INVALID_MAPPING_HEADER";
      throw error;
    }
    if (field && !CANONICAL_FIELDS.includes(field)) {
      const error = new Error(`Unsupported canonical field: ${field}`);
      error.status = 400;
      error.code = "INVALID_CANONICAL_FIELD";
      throw error;
    }
    if (field && seenFields.has(field)) {
      const error = new Error(`Canonical field is mapped more than once: ${field}`);
      error.status = 400;
      error.code = "DUPLICATE_CANONICAL_FIELD";
      throw error;
    }

    seenHeaders.add(originalHeader);
    if (field) seenFields.add(field);
    return { originalHeader, field };
  });

  const missingHeader = headers.find((header) => !seenHeaders.has(header));
  if (missingHeader) {
    const error = new Error(`Mapping is missing source header: ${missingHeader}`);
    error.status = 400;
    error.code = "INCOMPLETE_MAPPING";
    throw error;
  }

  return normalized;
}

function createHeaderMappingService({ repository = defaultRepository } = {}) {
  async function loadContext({ businessAccountId, ingestionId }) {
    const ingestion = await repository.getIngestion({ businessAccountId, ingestionId });
    if (!ingestion) {
      const error = new Error("Ingestion not found");
      error.status = 404;
      throw error;
    }

    const headers = parseJson(ingestion.headers_json, null);
    if (!Array.isArray(headers)) {
      const error = new Error("Stored ingestion headers are invalid");
      error.status = 422;
      error.code = "INVALID_STORED_HEADERS";
      throw error;
    }

    const rows = (await repository.getSampleRows({ businessAccountId, ingestionId }))
      .map((row) => parseJson(row, {}));
    return {
      ingestion,
      headers,
      rows,
      datasetType: ingestion.dataset_type || "unknown",
      headerSignature: createHeaderSignature(headers)
    };
  }

  async function getWorkspace({ businessAccountId, ingestionId }) {
    const context = await loadContext({ businessAccountId, ingestionId });
    const existing = await repository.getDatasetMapping({ businessAccountId, ingestionId });
    const automatic = suggestMappings(context.headers, context.rows);

    if (existing?.confirmed_at) {
      const mappings = parseJson(existing.mapping_json, []);
      return {
        ingestionId: Number(ingestionId),
        datasetType: context.datasetType,
        status: "ready_for_validation",
        canonicalFields: CANONICAL_FIELDS,
        mappings: mappings.map((mapping) => ({
          ...mapping,
          confidence: 1,
          reason: "confirmed"
        })),
        summary: summarize({
          datasetType: context.datasetType,
          mappings,
          totalHeaders: context.headers.length
        }),
        reusedSavedMapping: false
      };
    }

    const saved = await repository.getSavedMapping({
      businessAccountId,
      headerSignature: context.headerSignature
    });
    const savedMappings = parseJson(saved?.mapping_json, []);
    const mappings = savedMappings.length
      ? applySavedTemplate(automatic, savedMappings)
      : automatic;

    return {
      ingestionId: Number(ingestionId),
      datasetType: context.datasetType,
      status: "ready_for_mapping",
      canonicalFields: CANONICAL_FIELDS,
      mappings,
      summary: summarize({
        datasetType: context.datasetType,
        mappings,
        totalHeaders: context.headers.length
      }),
      reusedSavedMapping: savedMappings.length > 0
    };
  }

  async function confirmMapping({ businessAccountId, ingestionId, mappings, saveTemplate = true }) {
    const context = await loadContext({ businessAccountId, ingestionId });
    const validatedMappings = validateMappings(context.headers, mappings);
    const suggestions = suggestMappings(context.headers, context.rows);
    const summary = summarize({
      datasetType: context.datasetType,
      mappings: validatedMappings,
      totalHeaders: context.headers.length
    });

    await repository.saveMapping({
      businessAccountId,
      ingestionId,
      mappings: validatedMappings,
      suggestions,
      coverage: summary,
      headerSignature: context.headerSignature,
      saveTemplate: Boolean(saveTemplate)
    });

    return {
      ingestionId: Number(ingestionId),
      datasetType: context.datasetType,
      status: "ready_for_validation",
      canonicalFields: CANONICAL_FIELDS,
      mappings: validatedMappings.map((mapping) => ({
        ...mapping,
        confidence: 1,
        reason: "confirmed"
      })),
      summary,
      savedAsTemplate: Boolean(saveTemplate)
    };
  }

  return { getWorkspace, confirmMapping };
}

const service = createHeaderMappingService();

module.exports = {
  createHeaderMappingService,
  createHeaderSignature,
  validateMappings,
  getMappingWorkspace: service.getWorkspace,
  confirmHeaderMapping: service.confirmMapping
};
