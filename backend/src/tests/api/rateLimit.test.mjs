import request from "supertest";
import { describe, expect, it } from "vitest";
import app from "../../../app.js";

describe("alpha rate limits", () => {
  it("does not throttle status polling the way uploads are throttled", async () => {
    // Unauthenticated requests are refused with 401 by auth, never 429, however many times status is polled.
    let last = 0;
    for (let i = 0; i < 130; i += 1) last = (await request(app).get("/api/alpha/analyses/x")).status;
    expect(last).toBe(401);
  });
});
