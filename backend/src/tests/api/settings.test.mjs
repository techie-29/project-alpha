import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";
import routesModule from "../../../routes/settingsRoutes.js";

const { createSettingsRouter } = routesModule;

function appWith(dependencies) {
  const app = express(); app.use(express.json());
  app.use((req, res, next) => { req.user = { id: 7 }; next(); });
  app.use("/api/settings", createSettingsRouter(dependencies));
  app.use((error, req, res, next) => res.status(error.status || 500).json({ message: error.message }));
  return app;
}

describe("settings API", () => {
  it("never accepts a business id from the client", async () => {
    const update = vi.fn(async () => ({ businessName: "Northwind" }));
    const body = { businessName: "Northwind", currencyCode: "USD", timezone: "UTC", dateFormat: "YYYY-MM-DD", businessAccountId: 999 };
    const response = await request(appWith({ get: vi.fn(), update, changePassword: vi.fn() })).patch("/api/settings").send(body);
    expect(response.status).toBe(200);
    expect(update).toHaveBeenCalledWith({ businessAccountId: 7, body });
  });
});
