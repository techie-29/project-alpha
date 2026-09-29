const { transformValidatedRows } = require("../engine/transform/transformRows");
const { calculateQualityScore } = require("../engine/quality/qualityScore");
const defaultRepository = require("../../services/transformationPersistenceService");

function dataQuality(input) {
  const totalRows = input.rows.length || 1;
  const duplicateRows = new Set();
  const criticalMissingRows = new Set();
  input.rows.forEach((row) => row.issues.forEach((issue) => {
    if (issue.code === "DUPLICATE_ROW") duplicateRows.add(row.sourceRowNumber);
    if (issue.code === "REQUIRED_MISSING") criticalMissingRows.add(row.sourceRowNumber);
  }));
  return calculateQualityScore({
    validationSuccessRate: input.validationSummary.validationSuccessRate,
    mappingCoverage: input.mappingCoverage,
    duplicateRate: duplicateRows.size / totalRows,
    criticalFieldCompleteness: 1 - criticalMissingRows.size / totalRows
  });
}

function createTransformationService({ repository = defaultRepository } = {}) {
  async function runTransformation({ businessAccountId, ingestionId }) {
    const input = await repository.loadTransformationInput({ businessAccountId, ingestionId });
    if (!input) {
      const error = new Error("Ingestion not found");
      error.status = 404;
      throw error;
    }
    if (!input.validationSummary) {
      const error = new Error("Run validation before transformation");
      error.status = 409;
      error.code = "VALIDATION_REQUIRED";
      throw error;
    }

    const result = transformValidatedRows({
      rows: input.rows,
      datasetType: input.datasetType,
      datasetId: Number(ingestionId),
      businessId: businessAccountId
    });
    const quality = dataQuality(input);
    await repository.saveTransformationResult({
      businessAccountId,
      ingestionId,
      result,
      quality
    });
    return {
      ingestionId: Number(ingestionId),
      status: "ready_for_analytics",
      summary: result.summary,
      quality,
      examples: result.examples
    };
  }

  async function getTransformation({ businessAccountId, ingestionId }) {
    const result = await repository.getTransformationResult({ businessAccountId, ingestionId });
    if (!result) {
      const error = new Error("Ingestion not found");
      error.status = 404;
      throw error;
    }
    return result.pending
      ? { ingestionId: Number(ingestionId), status: "not_started" }
      : { ingestionId: Number(ingestionId), ...result };
  }

  return { runTransformation, getTransformation };
}

const service = createTransformationService();
module.exports = {
  createTransformationService,
  dataQuality,
  runTransformation: service.runTransformation,
  getTransformation: service.getTransformation
};
