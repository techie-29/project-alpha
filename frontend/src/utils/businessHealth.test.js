import { describe, expect, it } from "vitest";
import { businessHealth } from "./businessHealth";

const tiles = [
  { metric: "revenue", value: 1000, vs_last_year: { change: 0.1, label: "Oct 2025" } },
  { metric: "margin", value: 0.15 },
  { metric: "repeat_rate", value: 0.6 }, { metric: "customers", value: 100 }, { metric: "quiet_customers", value: 10 },
  { metric: "rate:x", label: "Returned rate (status)", value: 0.1 },
  { metric: "out_of_stock", value: 2 }, { metric: "products_sold", value: 20 },
];
describe("business health", () => {
  const h = businessHealth(tiles, [{ tone: "risk" }, { tone: "risk" }, { tone: "strength" }]);
  it("scores each part by its fixed thresholds", () => {
    const s = Object.fromEntries(h.parts.map((p) => [p.id, p.score]));
    expect(s).toEqual({ growth: 75, margin: 70, customers: 90, problems: 60, stock: 70, risks: 80 });
  });
  it("weights the parts and names the one that would raise the score most", () => {
    expect(h.score).toBe(74); expect(h.label).toBe("Steady");
    expect(["growth", "margin", "problems"]).toContain(h.raise.id); expect(h.raise.gain).toBeGreaterThan(0);
  });
  it("skips what the data cannot measure, and gives up with too little", () => {
    const only = businessHealth([{ metric: "revenue", value: 1, last_period: { change: 0, label: "a", previous_label: "b" } }], []);
    expect(only.parts.map((p) => p.id)).toEqual(["growth", "risks"]); expect(only.missing).toContain("margin");
    expect(businessHealth([], [])).toBeNull();
  });
});
