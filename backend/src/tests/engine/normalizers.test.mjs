import { describe, expect, it } from "vitest";
import normalizersModule from "../../engine/transform/normalizers.js";
import dateModule from "../../engine/transform/dateNormalizer.js";

const { parseNumber, normalizeText, normalizeStatus, productKey } = normalizersModule;
const { detectDateOrder, parseDate } = dateModule;

describe("transformation normalizers", () => {
  it("parses local and currency number formats", () => {
    expect(parseNumber("₹1,234.50")).toBe(1234.5);
    expect(parseNumber("1.234,50")).toBe(1234.5);
    expect(parseNumber("12,5")).toBe(12.5);
    expect(parseNumber("1,234,567")).toBe(1234567);
    expect(parseNumber("(200)")).toBe(-200);
    expect(parseNumber("N/A")).toBeNull();
  });

  it("normalizes text, statuses, and product keys", () => {
    expect(normalizeText("  Trail   Helmet ")).toBe("Trail Helmet");
    expect(normalizeStatus("Complete")).toBe("completed");
    expect(productKey({ sku: " H-1 ", product_name: "Helmet" })).toBe("h-1");
  });

  it("detects one date order per column", () => {
    expect(detectDateOrder(["13/09/2026", "01/09/2026"]).order).toBe("DMY");
    expect(detectDateOrder(["09/13/2026", "09/01/2026"]).order).toBe("MDY");
    expect(detectDateOrder(["01/09/2026"]).reason).toBe("ambiguous");
  });

  it("parses valid dates without timezone shifts", () => {
    expect(parseDate("2026-09-01")).toBe("2026-09-01");
    expect(parseDate("01/09/26", "DMY")).toBe("2026-09-01");
    expect(parseDate("Sep 1, 26")).toBe("2026-09-01");
    expect(parseDate("31/02/26", "DMY")).toBeNull();
    expect(parseDate("01/09/26")).toBeNull();
  });
});
