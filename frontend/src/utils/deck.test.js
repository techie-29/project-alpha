import { describe, expect, it } from "vitest";
import { buildDeck } from "./deck";

const tile = (metric, label, value, extra = {}) => ({ metric, label, value, fmt: metric === "margin" ? "pct" : "money", polarity: 1, last_period: { change: 0.1, label: "Oct", previous_label: "Sep" }, ...extra });
const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"].map((m) => `${m} 2026`);
const report = {
  generated_at: "2026-11-01T10:00:00Z", files: [{ name: "a" }],
  overview: { tiles: [tile("revenue", "Revenue", 1000), tile("profit", "Profit", 400), tile("orders", "Orders", 50, { fmt: "number" })],
    sections: [{ charts: [{ id: "c", type: "line", metric: "revenue", fmt: "money", unit: "", grains: { month: { x: months, series: [{ name: "Revenue", values: [5, 6, 7, 9, 8, 10] }] } },
      forecast: { status: "ok", x: ["Jul 2026"], mid: [10], low: [8], high: [12], last_actual: "Jun 2026", total: { mid: 10, low: 8, high: 12 }, backtest: { error: 0.06, grade: "fair" } } }] }] },
  briefing: { first_actions: [{ insight_id: "i1", title: "Fix returns", action: "Check packing", impact: 500 }] },
  data_check: { rows: { ok: 90, fixed: 5, flagged: 3, left_out: 2 }, headline: "100 rows" },
};
const view = { currency: "", cards: [
  { id: "1", insight_id: "i1", tone: "risk", headline: "Returns are high for Web", points: ["12% for Web against 3%. More text."], money: { amount: 500 }, chart_data: { type: "bar", title: "t", fmt: "pct", rows: [{ group: "Web", value: 0.12 }, { group: "Store", value: 0.03 }] }, look_into: "Check packing" },
  { id: "2", tone: "strength", headline: "Margin is higher for Snacks", points: ["Good."] }] };

describe("deck", () => {
  const d = buildDeck(report, view, { business: "Acme", presenter: "Sam" });
  it("builds the slides in a sensible order, each with notes", () => {
    expect(d.map((s) => s.id)).toEqual(["title", "snapshot", "sales", "risk1", "good", "forecast", "actions", "quality", "close"]);
    expect(d.every((s) => s.notes && s.notes.length > 20)).toBe(true);
    expect(d[0].title).toBe("Acme: business review"); expect(d[0].presenter).toBe("Sam");
  });
  it("puts real numbers in the problem and forecast slides", () => {
    const risk = d.find((s) => s.id === "risk1"); expect(risk.chart.rows).toHaveLength(2); expect(risk.action).toBe("Check packing");
    const f = d.find((s) => s.id === "forecast"); expect(f.trust).toEqual({ error: 6, grade: "fair" }); expect(f.notes).toMatch(/off by about 6%/);
  });
  it("leaves out slides it has nothing for", () => {
    const bare = buildDeck({ ...report, overview: { tiles: report.overview.tiles, sections: [] } }, { currency: "", cards: [] }, {});
    expect(bare.map((s) => s.id)).not.toContain("forecast"); expect(bare.map((s) => s.id)).not.toContain("risk1");
  });
});
