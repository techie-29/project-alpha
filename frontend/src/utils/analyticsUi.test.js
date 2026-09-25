import { describe, expect, it } from "vitest";
import { queryString } from "../services/analyticsApi";
import { formatPercent, titleCase } from "./formatters";

describe("analytics UI utilities", () => {
  it("serializes only active filters", () => {
    expect(queryString({ preset: "monthly", product: "trail helmet", customer: "", datasetId: null }))
      .toBe("?preset=monthly&product=trail+helmet");
  });

  it("formats ratios and canonical labels for display", () => {
    expect(formatPercent(0.125)).toBe("12.5%");
    expect(titleCase("out_of_stock")).toBe("Out Of Stock");
  });
});
