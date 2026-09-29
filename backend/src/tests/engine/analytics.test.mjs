import { describe, expect, it } from "vitest";
import kpiModule from "../../engine/analytics/kpis.js";
import inventoryModule from "../../engine/analytics/inventory.js";
import comparisonModule from "../../engine/analytics/comparisons.js";

const { computeKpis } = kpiModule;
const { latestStockSnapshots, daysOfCover } = inventoryModule;
const { compareValues } = comparisonModule;

const sales = [
  { order_id: "A1", order_date: "2026-09-01", product_key: "helmet", quantity: 2, revenue: 200, cost_price: 60, profit: 80, customer_key: "c1", status: "completed" },
  { order_id: "A1", order_date: "2026-09-01", product_key: "gloves", quantity: 1, revenue: 50, cost_price: 20, profit: 30, customer_key: "c1", status: "completed" },
  { order_id: "A2", order_date: "2026-09-02", product_key: "helmet", quantity: 1, revenue: 100, cost_price: 60, profit: 40, customer_key: "c2", status: "cancelled" }
];

describe("analytics KPIs", () => {
  it("computes KPI values and sub-KPIs from structured records", () => {
    const result = computeKpis({
      sales,
      previousSales: [{ order_id: "P1", order_date: "2026-08-01", quantity: 1, revenue: 175, customer_key: "c1", profit: 50 }],
      stock: [
        { product_key: "helmet", stock_qty: 8, reorder_level: 12, stock_status: "low_stock", stock_as_of_date: "2026-09-20" },
        { product_key: "gloves", stock_qty: 0, reorder_level: 5, stock_status: "out_of_stock", stock_as_of_date: "2026-09-20" }
      ]
    });

    expect(result.revenue).toMatchObject({ value: 350, dailyAverage: 175 });
    expect(result.revenue.previousPeriod.percentage).toBe(1);
    expect(result.orders).toMatchObject({ value: 2, completed: 1, cancelled: 1 });
    expect(result.units).toMatchObject({ value: 4, perOrder: 2 });
    expect(result.averageOrderValue.value).toBe(175);
    expect(result.grossProfit).toMatchObject({ value: 150, totalCost: 200 });
    expect(result.customers).toMatchObject({ value: 2, new: 1, returning: 1 });
    expect(result.inventory).toMatchObject({ products: 2, totalUnits: 8, lowStock: 1, outOfStock: 1 });
  });

  it("returns unavailable states instead of fake zeroes", () => {
    const result = computeKpis({ sales: [{ product_key: "helmet" }] });
    expect(result.revenue.available).toBe(false);
    expect(result.grossProfit.reason).toMatch(/cost_price/);
    expect(result.inventory.available).toBe(false);
  });

  it("uses only the latest stock snapshot per product", () => {
    const latest = latestStockSnapshots([
      { product_key: "helmet", stock_qty: 20, stock_as_of_date: "2026-09-01", source_row_number: 2 },
      { product_key: "helmet", stock_qty: 8, stock_as_of_date: "2026-09-20", source_row_number: 3 }
    ]);
    expect(latest).toHaveLength(1);
    expect(latest[0].stock_qty).toBe(8);
  });

  it("handles comparisons and days of cover honestly", () => {
    expect(compareValues(120, 100).percentage).toBe(0.2);
    expect(compareValues(10, 0).percentage).toBeNull();
    expect(daysOfCover({ stock: 8, unitsSoldInWindow: 39, windowDays: 30 })).toBeCloseTo(6.15, 1);
    expect(daysOfCover({ stock: 8, unitsSoldInWindow: 0 })).toBeNull();
  });
});
