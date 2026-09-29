import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";
import routesModule from "../../../routes/datasetLibraryRoutes.js";

const { createDatasetLibraryRouter } = routesModule;

function appWith(dependencies) {
  const app = express();
  app.use(express.json());
  app.use((req, res, next) => { req.user = { id: 7 }; next(); });
  app.use("/api/datasets", createDatasetLibraryRouter(dependencies));
  app.use((error, req, res, next) => res.status(error.status || 500).json({ message: error.message }));
  return app;
}

describe("dataset library API", () => {
  it("lists only the authenticated business datasets", async () => {
    const list = vi.fn(async () => [{ id: 12 }]);
    const response = await request(appWith({ list, get: vi.fn(), setIncluded: vi.fn() })).get("/api/datasets");
    expect(response.status).toBe(200);
    expect(list).toHaveBeenCalledWith({ businessAccountId: 7 });
  });

  it("passes an inclusion toggle through authenticated scope", async () => {
    const setIncluded = vi.fn(async (input) => ({ ingestionId: 12, included: input.included }));
    const response = await request(appWith({ list: vi.fn(), get: vi.fn(), setIncluded }))
      .patch("/api/datasets/12/inclusion").send({ included: false });
    expect(response.status).toBe(200);
    expect(setIncluded).toHaveBeenCalledWith({ businessAccountId: 7, ingestionId: "12", included: false });
  });

  it("streams a tenant-scoped normalized export", async () => {
    const exportDataset = vi.fn(async () => ({ filename: "sales-sales.csv", mime: "text/csv", buffer: Buffer.from("order_id\nA1") }));
    const response = await request(appWith({ list: vi.fn(), get: vi.fn(), setIncluded: vi.fn(), exportDataset }))
      .get("/api/datasets/12/export?type=sales&format=csv");
    expect(response.status).toBe(200);
    expect(response.headers["content-disposition"]).toContain("sales-sales.csv");
    expect(exportDataset).toHaveBeenCalledWith({ businessAccountId: 7, ingestionId: "12", type: "sales", format: "csv" });
  });
});
