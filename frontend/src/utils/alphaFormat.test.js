import { describe, expect, it } from "vitest";
import { amount, buildConfirmations, cellText, fileSize, num, percent, signedPercent } from "./alphaFormat";

describe("alpha formatting", () => {
  it("shortens big numbers and keeps small ones readable", () => {
    expect(num(1234567)).toBe("1.23M");
    expect(num(15000)).toBe("15.0K");
    expect(num(842.4)).toBe("842");
    expect(num(null)).toBe("—");
    expect(num(NaN)).toBe("—");
  });
  it("attaches a currency without ever mixing them", () => {
    expect(amount(91428, "EUR")).toBe("EUR 91.4K");
    expect(amount(5, "")).toBe("5");
  });
  it("formats shares and changes", () => {
    expect(percent(0.256)).toBe("26%");
    expect(signedPercent(0.12)).toBe("+12%");
    expect(signedPercent(-0.034, 1)).toBe("-3.4%");
    expect(signedPercent(undefined)).toBe("—");
  });
  it("formats sizes and cells", () => {
    expect(fileSize(52_000_000)).toBe("49.6 MB");
    expect(cellText("2021-12-22T00:00:00")).toBe("2021-12-22");
    expect(cellText(null)).toBe("");
    expect(cellText(3.14159)).toBe("3.14");
  });
  it("builds the confirmation payload", () => {
    expect(buildConfirmations({ roles: { "a.csv::x": "id" } })).toEqual({ columns: { "a.csv::x": "id" }, links: {}, time_col: {}, rows_in_time_order: {} });
  });
});
