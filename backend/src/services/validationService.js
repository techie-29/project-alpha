const { validateRows } = require("../engine/validation/validateRows");
const defaultRepository = require("../../services/validationPersistenceService");

function publicResult(ingestionId, result) {
  return {
    ingestionId: Number(ingestionId),
    status: "ready_for_transformation",
    summary: result.summary,
    dateOrders: result.dateOrders,
    rows: result.rows.slice(0, 50),
    issues: result.issues.slice(0, 200),
    returnedRowCount: Math.min(50, result.rows.length),
    returnedIssueCount: Math.min(200, result.issues.length)
  };
}

function createValidationService({ repository = defaultRepository } = {}) {
  async function runValidation({ businessAccountId, ingestionId }) {
    const input = await repository.loadValidationInput({ businessAccountId, ingestionId });
    if (!input) {
      const error = new Error("Ingestion not found");
      error.status = 404;
      throw error;
    }
    if (!Array.isArray(input.mappings)) {
      const error = new Error("Confirm header mapping before validation");
      error.status = 409;
      error.code = "MAPPING_REQUIRED";
      throw error;
    }

    const result = validateRows({
      rawRows: input.rawRows,
      mappings: input.mappings,
      datasetType: input.datasetType
    });
    await repository.saveValidationResult({ businessAccountId, ingestionId, result });
    return publicResult(ingestionId, result);
  }

  async function getValidation({ businessAccountId, ingestionId }) {
    const result = await repository.getValidationResult({ businessAccountId, ingestionId });
    if (!result) {
      const error = new Error("Ingestion not found");
      error.status = 404;
      throw error;
    }
    if (result.pending) {
      return { ingestionId: Number(ingestionId), status: "not_started" };
    }
    return { ingestionId: Number(ingestionId), ...result };
  }

  return { runValidation, getValidation };
}

const service = createValidationService();
module.exports = {
  createValidationService,
  runValidation: service.runValidation,
  getValidation: service.getValidation
};
