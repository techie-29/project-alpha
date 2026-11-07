import { describe, expect, it } from "vitest";
import { buildConfirmations, mappedConcepts, cellText, change, compact, fileSize, fmtValue, signedPct } from "./alphaFormat";

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
    expect(fmtValue(20.18, "days", "min")).toBe("20.2 min");
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
  it("sends 'Keep it', custom names and cleaning choices only when the owner made them", () => {
    const out = buildConfirmations({ modes: { "f::a": "keep", "f::b": "custom", "f::c": "custom" }, rename: { "f::b": "  Joined On ", "f::c": " ", "f::a": "ignored" },
                                     fixes: { f: { invalid_date: "remove" } }, mapped: { "f::age": "age" } });
    expect(out.keep).toEqual({ "f::a": true });
    expect(out.rename).toEqual({ "f::b": "Joined On" });          // an empty custom name is ignored, and a name only counts in custom mode
    expect(out.fixes).toEqual({ f: { invalid_date: "remove" } });
    expect(out.mapped).toEqual({ "f::age": "age" });
  });
  it("tells the engine what every column was read as, with the owner's change first and 'Keep it' as a plain column", () => {
    const reading = { files: [{ name: "f", columns: [{ name: "age", concept: "age", type: "measure" }, { name: "amt", original: "amount", concept: "revenue", type: "measure" },
                                                       { name: "city", concept: "location", type: "category" }, { name: "signup", concept: "signup_date", type: "time" }] }] };
    expect(mappedConcepts(reading, { concepts: { "f::age": "rating" }, modes: { "f::city": "keep" } }))
      .toEqual({ "f::age": "rating", "f::amount": "revenue", "f::city": "group", "f::signup": "signup_date" });
  });
});
