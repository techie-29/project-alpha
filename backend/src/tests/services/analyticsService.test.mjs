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
});
