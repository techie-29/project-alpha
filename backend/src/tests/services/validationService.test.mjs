import { describe, expect, it, vi } from "vitest";
import serviceModule from "../../services/validationService.js";

const { createValidationService } = serviceModule;

describe("validation service", () => {
  it("validates mapped rows and persists every outcome", async () => {
    const repository = {
      loadValidationInput: vi.fn(async () => ({
        datasetType: "sales",
        mappings: [
          { originalHeader: "Date", field: "order_date" },
          { originalHeader: "Item", field: "product_name" },
          { originalHeader: "Qty", field: "quantity" },
          { originalHeader: "Price", field: "unit_price" }
        ],
        rawRows: [
          { sourceRowNumber: 2, rawData: { Date: "2026-09-01", Item: "Helmet", Qty: 2, Price: 100 } },
          { sourceRowNumber: 3, rawData: { Date: "bad", Item: "Gloves", Qty: 1, Price: 50 } }
        ]
      })),
      saveValidationResult: vi.fn(async () => {}),
      getValidationResult: vi.fn()
    };
    const service = createValidationService({ repository });

    const result = await service.runValidation({ businessAccountId: 7, ingestionId: 12 });

    expect(result.summary).toMatchObject({ totalRows: 2, skippedRows: 1 });
    expect(repository.saveValidationResult).toHaveBeenCalledWith(expect.objectContaining({
      businessAccountId: 7,
      ingestionId: 12,
      result: expect.objectContaining({ rows: expect.any(Array), issues: expect.any(Array) })
    }));
  });

  it("requires a confirmed mapping", async () => {
    const repository = {
      loadValidationInput: vi.fn(async () => ({ mappings: null })),
      saveValidationResult: vi.fn(),
      getValidationResult: vi.fn()
    };
    const service = createValidationService({ repository });

    await expect(service.runValidation({ businessAccountId: 7, ingestionId: 12 }))
      .rejects.toMatchObject({ code: "MAPPING_REQUIRED", status: 409 });
  });
});
