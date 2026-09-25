import { describe, expect, it } from "vitest";
import transformModule from "../../engine/transform/transformRows.js";

const { deriveStockStatus, transformValidatedRows } = transformModule;

describe("transformation engine", () => {
  it("computes revenue and profit while preserving evidence", () => {
    const result = transformValidatedRows({
      datasetType: "sales",
      datasetId: 12,
      businessId: 7,
      rows: [{
        sourceRowNumber: 42,
        status: "repaired",
        repairedFields: ["order_date"],
        canonical: {
          order_id: "A1001", order_date: "2026-09-01", product_name: "Trail Helmet",
          quantity: 2, unit_price: 1500, discount: 0, cost_price: 900,
          customer_email: "Priya@Example.com", status: "Complete"
        },
        rawValues: { "Item Name": "Trail Helmet", Date: "01/09/26" }
      }]
    });

    expect(result.sales[0]).toMatchObject({
      revenue: 3000,
      profit: 1200,
      customer_key: "priya@example.com",
      product_key: "trail helmet",
      status: "completed",
      source_row_index: 42
    });
    expect(result.sales[0].computed_fields).toEqual(["revenue", "profit"]);
    expect(result.sales[0].raw_values.Date).toBe("01/09/26");
  });

  it("never reports missing profit as zero", () => {
    const result = transformValidatedRows({
      datasetType: "sales", datasetId: 12, businessId: 7,
      rows: [{ sourceRowNumber: 2, status: "valid", repairedFields: [], rawValues: {}, canonical: { product_name: "Helmet", quantity: 1, unit_price: 100 } }]
    });
    expect(result.sales[0].revenue).toBe(100);
    expect(result.sales[0].profit).toBeNull();
  });

  it("derives stock health from current stock and reorder level", () => {
    expect(deriveStockStatus(0, 10)).toBe("out_of_stock");
    expect(deriveStockStatus(8, 12)).toBe("low_stock");
    expect(deriveStockStatus(20, 12)).toBe("healthy");
    expect(deriveStockStatus(null, 12)).toBeNull();
  });

  it("excludes skipped rows from normalized storage output", () => {
    const result = transformValidatedRows({
      datasetType: "inventory", datasetId: 12, businessId: 7,
      rows: [{ sourceRowNumber: 2, status: "skipped", canonical: { product_name: "Helmet", stock_qty: -1 }, rawValues: {} }]
    });
    expect(result.summary.acceptedRows).toBe(0);
    expect(result.stock).toEqual([]);
  });

  it("creates structured product and supplier records", () => {
    const product = transformValidatedRows({
      datasetType: "products", datasetId: 12, businessId: 7,
      rows: [{ sourceRowNumber: 2, status: "valid", repairedFields: [], rawValues: {}, canonical: { sku: "H-1", product_name: "Helmet", unit_price: 100 } }]
    });
    const supplier = transformValidatedRows({
      datasetType: "suppliers", datasetId: 13, businessId: 7,
      rows: [{ sourceRowNumber: 2, status: "valid", repairedFields: [], rawValues: {}, canonical: { supplier_name: "Peak Supply" } }]
    });
    expect(product.products[0].product_key).toBe("h-1");
    expect(supplier.suppliers[0].supplier_key).toBe("peak supply");
  });
});
