import { describe, expect, it } from "vitest";
import { baseline, simulate } from "./whatIf";

const b = baseline([{ label: "Revenue", value: 1000 }, { label: "Profit", value: 400 }, { label: "Orders", value: 100 }]);
describe("what-if", () => {
  it("reads the baseline and returns it unchanged with no moves", () => {
    expect(b).toMatchObject({ revenue: 1000, cost: 600, profit: 400 });
    expect(simulate(b, {})).toMatchObject({ revenue: 1000, profit: 400, margin: 0.4, orders: 100 });
  });
  it("a price rise lifts revenue and profit when customers do not react", () => {
    const r = simulate(b, { price: 10, reaction: "same" });
    expect(r.revenue).toBeCloseTo(1100); expect(r.profit).toBeCloseTo(500);
  });
  it("customers buying less can cancel the gain", () => {
    const r = simulate(b, { price: 10, reaction: "lot" });
    expect(r.volume).toBeCloseTo(0.85); expect(r.orders).toBeCloseTo(85);
  });
  it("discount and cost moves hit profit; no revenue means no baseline", () => {
    expect(simulate(b, { discount: 10 }).profit).toBeCloseTo(300);
    expect(simulate(b, { cost: 10 }).profit).toBeCloseTo(340);
    expect(baseline([{ label: "Orders", value: 5 }])).toBeNull();
  });
});
