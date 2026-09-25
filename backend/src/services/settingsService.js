const bcrypt = require("bcrypt");
const { z } = require("zod");
const defaultRepository = require("../../services/settingsPersistenceService");

const preferencesSchema = z.object({
  businessName: z.string().trim().min(2).max(120),
  currencyCode: z.enum(["USD", "EUR", "GBP", "INR", "AUD", "CAD"]),
  timezone: z.string().trim().min(1).max(80),
  dateFormat: z.enum(["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"])
});
const passwordSchema = z.object({
  currentPassword: z.string().min(1).max(128),
  newPassword: z.string().min(8).max(128)
});

function inputError(result) {
  const error = new Error(result.error.issues.map((issue) => issue.message).join("; "));
  error.status = 400;
  error.code = "INVALID_SETTINGS";
  return error;
}

function createSettingsService({ repository = defaultRepository, passwordHasher = bcrypt } = {}) {
  async function get({ businessAccountId }) {
    const row = await repository.getSettings({ businessAccountId });
    if (!row) { const error = new Error("Business account not found"); error.status = 404; throw error; }
    return {
      id: row.id, businessName: row.business_name, email: row.email,
      currencyCode: row.currency_code, timezone: row.timezone, dateFormat: row.date_format
    };
  }

  async function update({ businessAccountId, body }) {
    const input = preferencesSchema.safeParse(body);
    if (!input.success) throw inputError(input);
    const updated = await repository.updatePreferences({ businessAccountId, ...input.data });
    if (!updated) { const error = new Error("Business account not found"); error.status = 404; throw error; }
    return get({ businessAccountId });
  }

  async function changePassword({ businessAccountId, body }) {
    const input = passwordSchema.safeParse(body);
    if (!input.success) throw inputError(input);
    const currentHash = await repository.getPasswordHash({ businessAccountId });
    if (!currentHash || !(await passwordHasher.compare(input.data.currentPassword, currentHash))) {
      const error = new Error("Current password is incorrect"); error.status = 400; error.code = "INVALID_CURRENT_PASSWORD"; throw error;
    }
    const passwordHash = await passwordHasher.hash(input.data.newPassword, 10);
    await repository.updatePassword({ businessAccountId, passwordHash });
    return { changed: true };
  }

  return { get, update, changePassword };
}

const service = createSettingsService();
module.exports = { createSettingsService, preferencesSchema, passwordSchema, get: service.get, update: service.update, changePassword: service.changePassword };
