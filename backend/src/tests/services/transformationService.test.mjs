import { describe, expect, it, vi } from "vitest";
import serviceModule from "../../services/transformationService.js";

const { createTransformationService } = serviceModule;

describe("transformation service", () => {
  it("transforms, scores, and persists validated records", async () => {
    const repository = {
      loadTransformationInput: vi.fn(async () => ({
        datasetType: "sales",
        mappingCoverage: 1,
        validationSummary: { validationSuccessRate: 1 },
        rows: [{
          sourceRowNumber: 2, status: "valid", repairedFields: [], issues: [], rawValues: {},
          canonical: { order_date: "2026-09-01", product_name: "Helmet", quantity: 2, unit_price: 100 }
        }]
      })),
      saveTransformationResult: vi.fn(async () => {}),
      getTransformationResult: vi.fn()
    };
    const service = createTransformationService({ repository });

    const result = await service.runTransformation({ businessAccountId: 7, ingestionId: 12 });

    expect(result.summary.salesRecords).toBe(1);
    expect(result.examples.sales[0].revenue).toBe(200);
    expect(result.quality.score).toBe(100);
    expect(repository.saveTransformationResult).toHaveBeenCalled();
  });

  it("requires validation before storage", async () => {
    const repository = {
      loadTransformationInput: vi.fn(async () => ({ validationSummary: null })),
      saveTransformationResult: vi.fn(), getTransformationResult: vi.fn()
    };
    const service = createTransformationService({ repository });
    await expect(service.runTransformation({ businessAccountId: 7, ingestionId: 12 }))
      .rejects.toMatchObject({ code: "VALIDATION_REQUIRED" });
  });
});
