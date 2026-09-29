import request from "supertest";
import { describe, expect, it } from "vitest";
import app from "../../../app.js";

describe("application health", () => {
  it("boots the complete Express application and exposes health status", async () => {
    const response = await request(app).get("/api/health");
    expect(response.status).toBe(200);
    expect(response.body).toEqual({ success: true, message: "Project Alpha backend is running" });
    expect(response.headers["x-content-type-options"]).toBe("nosniff");
  });
});
