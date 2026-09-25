import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";
import routesModule from "../../../routes/analyticsRoutes.js";

const { createAnalyticsRouter } = routesModule;

function appWith(getAnalytics) {
  const app = express();
  app.use((req, res, next) => { req.user = { id: 7 }; next(); });
  app.use("/api/analytics", createAnalyticsRouter({ getAnalytics }));
  app.use((error, req, res, next) => res.status(error.status || 500).json({ message: error.message }));
  return app;
}

describe("analytics API", () => {
  it("scopes overview requests to the authenticated tenant and passes filters", async () => {
    const getAnalytics = vi.fn(async () => ({ kpis: {}, intelligence: {} }));
    const response = await request(appWith(getAnalytics)).get("/api/analytics/overview?product=helmet&preset=weekly");
    expect(response.status).toBe(200);
    expect(getAnalytics).toHaveBeenCalledWith({ businessAccountId: 7, query: expect.objectContaining({ product: "helmet", preset: "weekly" }) });
  });

  it("returns purpose-specific insight data without exposing unrelated records", async () => {
    const getAnalytics = vi.fn(async () => ({
      period: { from: "2026-09-01", to: "2026-09-30" },
      intelligence: { insights: [{ id: "one" }], forecast: { ok: false }, anomalies: { available: false } }
    }));
    const response = await request(appWith(getAnalytics)).get("/api/analytics/insights");
    expect(response.status).toBe(200);
    expect(response.body.data.insights).toEqual([{ id: "one" }]);
    expect(response.body.data.kpis).toBeUndefined();
  });
});
