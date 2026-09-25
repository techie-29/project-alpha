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

  it("keeps usable rows and reports structurally broken rows", () => {
    const result = normalizeTable([
      ["Product", "Qty"],
      ["Helmet", 2],
      ["Gloves", 3, "unexpected"],
      ["Jacket", null]
    ]);

    expect(result.rows).toHaveLength(2);
    expect(result.skippedRows).toEqual([
      { sourceRowNumber: 3, reason: "extra_values" }
    ]);
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
