import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";
import routesModule from "../../../routes/headerMappingRoutes.js";

const { createHeaderMappingRouter } = routesModule;

function appWith(dependencies) {
  const app = express();
  app.use(express.json());
  app.use((req, res, next) => {
    req.user = { id: 7 };
    next();
  });
  app.use("/api/header-mapping", createHeaderMappingRouter(dependencies));
  app.use((error, req, res, next) => {
    res.status(error.status || 500).json({ success: false, code: error.code, message: error.message });
  });
  return app;
}

describe("header mapping API", () => {
  it("loads a business-scoped mapping workspace", async () => {
    const getWorkspace = vi.fn(async () => ({
      ingestionId: 12,
      status: "ready_for_mapping",
      mappings: [],
      summary: {},
      reusedSavedMapping: false
    }));
    const app = appWith({ getWorkspace, confirmMapping: vi.fn() });

    const response = await request(app).get("/api/header-mapping/12");

    expect(response.status).toBe(200);
    expect(getWorkspace).toHaveBeenCalledWith({ businessAccountId: 7, ingestionId: "12" });
  });

  it("passes manual corrections to the confirmation service", async () => {
    const confirmMapping = vi.fn(async () => ({
      ingestionId: 12,
      status: "ready_for_validation",
      mappings: [],
      summary: {}
    }));
    const app = appWith({ getWorkspace: vi.fn(), confirmMapping });
    const mappings = [{ originalHeader: "Qty", field: "quantity" }];

    const response = await request(app)
      .put("/api/header-mapping/12")
      .send({ mappings, saveTemplate: false });

    expect(response.status).toBe(200);
    expect(confirmMapping).toHaveBeenCalledWith({
      businessAccountId: 7,
      ingestionId: "12",
      mappings,
      saveTemplate: false
    });
  });
});
