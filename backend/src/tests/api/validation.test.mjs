import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";
import routesModule from "../../../routes/validationRoutes.js";

const { createValidationRouter } = routesModule;

function appWith(dependencies) {
  const app = express();
  app.use((req, res, next) => { req.user = { id: 7 }; next(); });
  app.use("/api/validation", createValidationRouter(dependencies));
  app.use((error, req, res, next) => res.status(error.status || 500).json({ message: error.message }));
  return app;
}

describe("validation API", () => {
  it("runs validation in the authenticated business scope", async () => {
    const runValidation = vi.fn(async () => ({
      ingestionId: 12,
      status: "ready_for_transformation",
      summary: { totalRows: 2 }
    }));
    const app = appWith({ runValidation, getValidation: vi.fn() });

    const response = await request(app).post("/api/validation/12/run");

    expect(response.status).toBe(200);
    expect(runValidation).toHaveBeenCalledWith({ businessAccountId: 7, ingestionId: "12" });
  });

  it("loads a persisted validation result", async () => {
    const getValidation = vi.fn(async () => ({ ingestionId: 12, status: "ready_for_transformation" }));
    const app = appWith({ runValidation: vi.fn(), getValidation });

    const response = await request(app).get("/api/validation/12");

    expect(response.status).toBe(200);
    expect(response.body.data.status).toBe("ready_for_transformation");
  });
});
