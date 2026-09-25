import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";
import routesModule from "../../../routes/transformationRoutes.js";

const { createTransformationRouter } = routesModule;

function appWith(dependencies) {
  const app = express();
  app.use((req, res, next) => { req.user = { id: 7 }; next(); });
  app.use("/api/transformation", createTransformationRouter(dependencies));
  app.use((error, req, res, next) => res.status(error.status || 500).json({ message: error.message }));
  return app;
}

describe("transformation API", () => {
  it("runs storage in the authenticated business scope", async () => {
    const runTransformation = vi.fn(async () => ({ ingestionId: 12, status: "ready_for_analytics" }));
    const app = appWith({ runTransformation, getTransformation: vi.fn() });
    const response = await request(app).post("/api/transformation/12/run");
    expect(response.status).toBe(200);
    expect(runTransformation).toHaveBeenCalledWith({ businessAccountId: 7, ingestionId: "12" });
  });
});
