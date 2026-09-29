import { describe, expect, it, vi } from "vitest";
import serviceModule from "../../services/analyticsService.js";

const { createAnalyticsService, normalizeFilters } = serviceModule;

describe("analytics service", () => {
  it("loads only the authenticated tenant and anchors the default period to its latest data", async () => {
    const repository = {
      loadAnalyticsData: vi.fn(async () => ({
        sales: [{ order_date: "2026-09-20", order_id: "A1", revenue: 100 }], stock: [], products: [], datasets: []
      }))
    };
    const service = createAnalyticsService({ repository });
    const result = await service.getAnalytics({ businessAccountId: 7 });
    expect(repository.loadAnalyticsData).toHaveBeenCalledWith({ businessAccountId: 7 });
    expect(result.period).toEqual({ from: "2026-09-01", to: "2026-09-20" });
  });

  it("rejects invalid filter values before querying data", () => {
    expect(() => normalizeFilters({ datasetId: "not-a-number" })).toThrow(/positive integer/);
    expect(() => normalizeFilters({ preset: "yearly" })).toThrow(/Period preset/);
  });

  it("traces a KPI back to normalized and raw source evidence", async () => {
    const repository = { loadAnalyticsData: vi.fn(async () => ({
      datasets: [], products: [], stock: [],
      sales: [{
        ingestion_id: 12, source_row_number: 7, source_file_name: "sales.csv",
        order_id: "A1", order_date: "2026-09-20", product_key: "helmet", quantity: "2", revenue: "200",
        raw_values: JSON.stringify({ Qty: "2", Sales: "$200" }), computed_fields: JSON.stringify(["revenue"]),
        repaired_fields: "[]", source_mapping: JSON.stringify([{ originalHeader: "Sales", field: "revenue" }])
      }]
    })) };
    const service = createAnalyticsService({ repository });
    const result = await service.getTraceability({ businessAccountId: 7, metric: "revenue", query: { preset: "daily" } });
    expect(result).toMatchObject({ metric: "revenue", total: 200, recordCount: 1 });
    expect(result.records[0]).toMatchObject({ sourceFile: "sales.csv", rawValues: { Qty: "2", Sales: "$200" } });
  });
});
