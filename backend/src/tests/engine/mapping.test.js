const { describe, it, expect } = require("vitest");
const { normalizeHeader } = require("../../engine/mapping/canonicalFields");
const {
  suggestHeaderMapping,
  suggestMappings
} = require("../../engine/mapping/suggestMapping");

describe("V3 header mapping", () => {
  it("normalizes common header styles", () => {
    expect(normalizeHeader(" Qty_Sold ")).toBe("qty sold");
  });

  it("maps exact aliases with certainty", () => {
    expect(suggestHeaderMapping("Qty Sold")).toEqual({
      field: "quantity",
      confidence: 1,
      reason: "alias"
    });
  });

  it("can suggest a close fuzzy match", () => {
    const result = suggestHeaderMapping("Custmer Email");
    expect(result.field).toBe("customer_email");
    expect(result.reason).toBe("fuzzy");
    expect(result.confidence).toBeGreaterThanOrEqual(0.85);
  });

  it("uses values as a fallback for an email column", () => {
    const result = suggestHeaderMapping("Contact", [
      "a@example.com",
      "b@example.com"
    ]);
    expect(result).toEqual({
      field: "customer_email",
      confidence: 0.8,
      reason: "value_sniff_email"
    });
  });

  it("keeps unsupported columns unmapped", () => {
    expect(suggestHeaderMapping("Favourite Colour", ["Blue", "Red"]).field).toBeNull();
  });

  it("returns a suggestion for every input header", () => {
    const rows = [{ "Item Name": "Helmet", "Qty Sold": 2 }];
    const result = suggestMappings(["Item Name", "Qty Sold"], rows);
    expect(result).toHaveLength(2);
    expect(result[0].field).toBe("product_name");
    expect(result[1].field).toBe("quantity");
  });
});
