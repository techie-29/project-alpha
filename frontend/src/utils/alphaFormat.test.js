import { describe, expect, it } from "vitest";
import { buildConfirmations, cellText, change, compact, fileSize, fmtValue, signedPct } from "./alphaFormat";

describe("alpha formatting", () => {
  it("compacts like the engine", () => {
    expect(compact(1234567)).toBe("1.23M");
    expect(compact(15000)).toBe("15.0K");
    expect(compact(null)).toBe("—");
  });
  it("formats by kind and never mixes currencies", () => {
    expect(fmtValue(88242761.78, "money", "USD")).toBe("USD 88.24M");
    expect(fmtValue(0.414, "pct")).toBe("41.4%");
    expect(fmtValue(3.677, "rating")).toBe("3.68");
    expect(fmtValue(4.56, "days")).toBe("4.6 days");
  });
  it("shows changes in points for rates and percent otherwise", () => {
    expect(change(0.012, "pct")).toBe("+1.2 pts");
    expect(change(-0.05, "money")).toBe("-5.0%");
    expect(signedPct(undefined)).toBe("—");
  });
  it("formats sizes, cells and confirmations", () => {
    expect(fileSize(52_000_000)).toBe("49.6 MB");
    expect(cellText("2021-12-22T00:00:00")).toBe("2021-12-22");
    expect(buildConfirmations({ concepts: { "a::b": "revenue" } })).toEqual({ concepts: { "a::b": "revenue" }, links: {}, columns: {}, rows_in_time_order: {} });
  });
});
