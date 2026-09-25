import { describe, expect, it, vi } from "vitest";
import serviceModule from "../../services/settingsService.js";

const { createSettingsService } = serviceModule;

describe("business settings service", () => {
  it("updates preferences in authenticated tenant scope", async () => {
    const repository = {
      updatePreferences: vi.fn(async () => true),
      getSettings: vi.fn(async () => ({ id: 7, business_name: "Northwind", email: "owner@example.com", currency_code: "GBP", timezone: "Europe/London", date_format: "DD/MM/YYYY" }))
    };
    const service = createSettingsService({ repository });
    const body = { businessName: "Northwind", currencyCode: "GBP", timezone: "Europe/London", dateFormat: "DD/MM/YYYY" };
    const result = await service.update({ businessAccountId: 7, body });
    expect(result).toMatchObject({ businessName: "Northwind", currencyCode: "GBP" });
    expect(repository.updatePreferences).toHaveBeenCalledWith({ businessAccountId: 7, ...body });
  });

  it("verifies the current password before storing a new hash", async () => {
    const repository = { getPasswordHash: vi.fn(async () => "old-hash"), updatePassword: vi.fn(async () => true) };
    const passwordHasher = { compare: vi.fn(async () => true), hash: vi.fn(async () => "new-hash") };
    const service = createSettingsService({ repository, passwordHasher });
    await expect(service.changePassword({ businessAccountId: 7, body: { currentPassword: "old-password", newPassword: "new-password" } })).resolves.toEqual({ changed: true });
    expect(repository.updatePassword).toHaveBeenCalledWith({ businessAccountId: 7, passwordHash: "new-hash" });
  });

  it("rejects an incorrect current password", async () => {
    const repository = { getPasswordHash: vi.fn(async () => "old-hash"), updatePassword: vi.fn() };
    const passwordHasher = { compare: vi.fn(async () => false), hash: vi.fn() };
    const service = createSettingsService({ repository, passwordHasher });
    await expect(service.changePassword({ businessAccountId: 7, body: { currentPassword: "wrong", newPassword: "new-password" } })).rejects.toMatchObject({ code: "INVALID_CURRENT_PASSWORD" });
    expect(repository.updatePassword).not.toHaveBeenCalled();
  });
});
