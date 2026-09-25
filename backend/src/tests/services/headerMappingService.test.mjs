import { describe, expect, it, vi } from "vitest";
import mappingServiceModule from "../../../services/headerMappingService.js";

const { createHeaderMappingService, createHeaderSignature, validateMappings } = mappingServiceModule;

function repository(overrides = {}) {
  return {
    getIngestion: vi.fn(async () => ({
      id: 12,
      headers_json: ["Order Date", "Qty Sold", "Item Name", "Selling Price"],
      dataset_type: "sales",
      status: "ready_for_mapping"
    })),
    getSampleRows: vi.fn(async () => [{
      "Order Date": "2026-09-01",
      "Qty Sold": 2,
      "Item Name": "Helmet",
      "Selling Price": 100
    }]),
    getDatasetMapping: vi.fn(async () => null),
    getSavedMapping: vi.fn(async () => null),
    saveMapping: vi.fn(async () => {}),
    ...overrides
  };
}

describe("header mapping service", () => {
  it("creates a stable signature regardless of header order", () => {
    expect(createHeaderSignature(["Qty Sold", "Item Name"]))
      .toBe(createHeaderSignature(["Item Name", "Qty Sold"]));
  });

  it("returns confidence, reasons, and required-field coverage", async () => {
    const service = createHeaderMappingService({ repository: repository() });

    const result = await service.getWorkspace({ businessAccountId: 7, ingestionId: 12 });

    expect(result.status).toBe("ready_for_mapping");
    expect(result.summary.coverage).toBe(1);
    expect(result.mappings[0]).toMatchObject({
      originalHeader: "Order Date",
      field: "order_date",
      confidence: 1
    });
  });

  it("reuses a saved template for the same header set", async () => {
    const repo = repository({
      getSavedMapping: vi.fn(async () => ({
        mapping_json: [
          { originalHeader: "Order Date", field: "order_date" },
          { originalHeader: "Qty Sold", field: "quantity" },
          { originalHeader: "Item Name", field: "product_name" },
          { originalHeader: "Selling Price", field: "unit_price" }
        ]
      }))
    });
    const service = createHeaderMappingService({ repository: repo });

    const result = await service.getWorkspace({ businessAccountId: 7, ingestionId: 12 });

    expect(result.reusedSavedMapping).toBe(true);
    expect(result.mappings.every((mapping) => mapping.reason === "saved_template")).toBe(true);
  });

  it("confirms and persists a complete manual mapping", async () => {
    const repo = repository();
    const service = createHeaderMappingService({ repository: repo });
    const mappings = [
      { originalHeader: "Order Date", field: "order_date" },
      { originalHeader: "Qty Sold", field: "quantity" },
      { originalHeader: "Item Name", field: "product_name" },
      { originalHeader: "Selling Price", field: "unit_price" }
    ];

    const result = await service.confirmMapping({
      businessAccountId: 7,
      ingestionId: 12,
      mappings,
      saveTemplate: true
    });

    expect(result.status).toBe("ready_for_validation");
    expect(repo.saveMapping).toHaveBeenCalledWith(expect.objectContaining({
      businessAccountId: 7,
      ingestionId: 12,
      mappings,
      saveTemplate: true
    }));
  });

  it("rejects duplicate canonical targets", () => {
    expect(() => validateMappings(["A", "B"], [
      { originalHeader: "A", field: "status" },
      { originalHeader: "B", field: "status" }
    ])).toThrowError(/more than once/i);
  });
});
