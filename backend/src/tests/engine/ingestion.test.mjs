import { describe, expect, it } from "vitest";
import normalizeModule from "../../engine/ingestion/normalizeTable.js";
import profileModule from "../../engine/ingestion/profileColumns.js";

const { makeUniqueHeaders, normalizeTable } = normalizeModule;
const { profileColumns } = profileModule;

describe("V3 ingestion engine", () => {
  it("renames duplicate headers instead of rejecting the dataset", () => {
    expect(makeUniqueHeaders(["Price", "price", "Product"]))
      .toEqual(["Price", "price_2", "Product"]);
  });

  it("repairs blank headers with stable fallback names", () => {
    expect(makeUniqueHeaders(["Product", null, "Product"]))
      .toEqual(["Product", "Column_2", "Product_2"]);
  });

  it("keeps usable rows and reports structurally broken rows", () => {
    const result = normalizeTable([
      ["Product", "Qty"],
      ["Helmet", 2],
      ["Gloves", 3, "unexpected"],
      ["Jacket", null]
    ]);

    expect(result.rows).toHaveLength(2);
    expect(result.sourceRowNumbers).toEqual([2, 4]);
    expect(result.skippedRows).toEqual([
      { sourceRowNumber: 3, reason: "extra_values" }
    ]);
  });

  it("keeps the real header when the first data row is structurally broken", () => {
    const result = normalizeTable([
      ["Product", "Qty"],
      ["Broken", 2, "unexpected"],
      ["Helmet", 1]
    ]);

    expect(result.headers).toEqual(["Product", "Qty"]);
    expect(result.rows).toEqual([{ Product: "Helmet", Qty: 1 }]);
    expect(result.skippedRows[0].sourceRowNumber).toBe(2);
  });

  it("enforces the configured row limit with an actionable error", () => {
    expect(() => normalizeTable([
      ["Product", "Qty"],
      ["Helmet", 2],
      ["Gloves", 3]
    ], { maxRows: 1 })).toThrowError(/maximum of 1 data rows/i);
  });

  it("profiles missing and mixed values", () => {
    const profile = profileColumns({
      headers: ["Qty"],
      rows: [{ Qty: 2 }, { Qty: null }, { Qty: "unknown" }]
    });

    expect(profile.columns[0]).toMatchObject({
      name: "Qty",
      detectedType: "mixed",
      missingCount: 1,
      nonMissingCount: 2
    });
  });
});
