import { describe, expect, it } from "vitest";
import authModule from "../../../routes/authRoutes.js";

const { registerSchema, loginSchema, validated } = authModule;

describe("authentication input validation", () => {
  it("normalizes valid registration input", () => {
    const result = validated(registerSchema, { businessName: "  Northwind  ", email: "OWNER@EXAMPLE.COM ", password: "long-password" });
    expect(result.data).toEqual({ businessName: "Northwind", email: "owner@example.com", password: "long-password" });
  });

  it("rejects weak passwords, invalid email, and oversized names", () => {
    expect(validated(registerSchema, { businessName: "A", email: "bad", password: "short" }).error).toBeTruthy();
    expect(validated(loginSchema, { email: "bad", password: "x" }).error).toBeTruthy();
  });
});
