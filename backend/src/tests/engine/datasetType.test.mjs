import { describe, expect, it } from "vitest";
import datasetTypeModule from "../../engine/ingestion/detectDatasetType.js";

const { detectDatasetType } = datasetTypeModule;

describe("dataset type detection", () => {
  it("detects a sales dataset from mapped business fields", () => {
    const result = detectDatasetType(
      ["Order ID", "Order Date", "Qty Sold", "Sales Amount"],
      [{ "Order ID": "A-1", "Order Date": "2026-09-01", "Qty Sold": 2, "Sales Amount": 100 }]
    );

    expect(result.type).toBe("sales");
    expect(result.evidence).toContain("order_id");
    expect(result.evidence).toContain("quantity");
  });

  it("detects inventory data", () => {
    const result = detectDatasetType(
      ["SKU", "Stock Level", "Reorder Point"],
      [{ SKU: "H-1", "Stock Level": 5, "Reorder Point": 10 }]
    );

    expect(result.type).toBe("inventory");
  });

  it("does not misclassify a supplier directory as customer data", () => {
    const result = detectDatasetType(
      ["Supplier Name", "Region", "Phone"],
      [{ "Supplier Name": "Peak Supply", Region: "North", Phone: "9000000001" }]
    );

    expect(result.type).toBe("suppliers");
  });

  it("returns unknown instead of guessing unsupported data", () => {
    expect(detectDatasetType(["Colour", "Comment"], []).type).toBe("unknown");
  });
});
