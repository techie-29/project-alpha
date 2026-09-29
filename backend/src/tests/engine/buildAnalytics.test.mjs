import { describe, expect, it } from "vitest";
import analyticsModule from "../../engine/analytics/buildAnalytics.js";

const { buildAnalytics, denseRevenueSeries, customerConcentration } = analyticsModule;

describe("analytics response builder", () => {
  it("builds adaptive analytics without double-counting stock snapshots", () => {
    const result = buildAnalytics({
      period: { from: "2026-09-01", to: "2026-09-30" },
      previous: { from: "2026-08-02", to: "2026-08-31" },
      datasets: [{ id: 1, filename: "sales.csv", qualityScore: 90 }],
      sales: [
        { ingestion_id: 1, order_id: "A1", order_date: "2026-09-10", product_key: "helmet", product_name: "Helmet", category: "Gear", quantity: 3, unit_price: 100, revenue: 300, profit: 120, customer_key: "c1" },
        { ingestion_id: 1, order_id: "P1", order_date: "2026-08-10", product_key: "helmet", quantity: 1, revenue: 100, profit: 20, customer_key: "c1" }
      ],
      stock: [
        { ingestion_id: 2, source_row_number: 2, product_key: "helmet", product_name: "Helmet", stock_qty: 20, reorder_level: 10, stock_as_of_date: "2026-09-01" },
        { ingestion_id: 2, source_row_number: 3, product_key: "helmet", product_name: "Helmet", stock_qty: 9, reorder_level: 10, stock_as_of_date: "2026-09-20" }
      ],
      products: []
    });

    expect(result.kpis.revenue.value).toBe(300);
    expect(result.kpis.inventory).toMatchObject({ products: 1, totalUnits: 9, lowStock: 1 });
    expect(result.inventory[0].daysOfCover).toBe(90);
    expect(result.products[0]).toMatchObject({ productKey: "helmet", abcClass: "A" });
    expect(result.provenance).toHaveLength(1);
  });

  it("returns honest unavailable states for unsupported areas", () => {
    const result = buildAnalytics({
      period: { from: "2026-09-01", to: "2026-09-30" },
      previous: { from: "2026-08-02", to: "2026-08-31" }
    });
    expect(result.kpis.revenue.available).toBe(false);
    expect(result.kpis.inventory.available).toBe(false);
    expect(result.intelligence.forecast.ok).toBe(false);
  });

  it("fills missing calendar dates with zero for intelligence functions", () => {
    expect(denseRevenueSeries([{ order_date: "2026-09-02", revenue: 5 }], "2026-09-01", "2026-09-03"))
      .toEqual([{ date: "2026-09-01", value: 0 }, { date: "2026-09-02", value: 5 }, { date: "2026-09-03", value: 0 }]);
    expect(customerConcentration([{ customer_key: "a", revenue: 90 }, { customer_key: "b", revenue: 10 }]).topTenPercentShare).toBe(0.9);
  });
});
