import { describe, expect, it } from "vitest";
import coverageModule from "../../engine/mapping/mappingCoverage.js";

const { calculateMappingCoverage } = coverageModule;

describe("mapping coverage", () => {
  it("supports alternative product and revenue fields for sales", () => {
    const result = calculateMappingCoverage({
      datasetType: "sales",
      totalHeaders: 4,
      mappings: [
        { field: "order_date" },
        { field: "quantity" },
        { field: "sku" },
        { field: "unit_price" }
      ]
    });

    expect(result.coverage).toBe(1);
    expect(result.missingCriticalFields).toEqual([]);
  });

  it("reports missing critical groups instead of inventing coverage", () => {
    const result = calculateMappingCoverage({
      datasetType: "inventory",
      totalHeaders: 3,
      mappings: [{ field: "product_name" }, { field: null }, { field: null }]
    });

    expect(result.coverage).toBe(0.5);
    expect(result.headerCoverage).toBeCloseTo(1 / 3, 4);
    expect(result.missingCriticalFields).toEqual(["stock_qty"]);
  });
});
