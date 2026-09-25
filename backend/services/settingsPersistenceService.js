const db = require("../config/db");

async function getSettings({ businessAccountId }) {
  const [rows] = await db.execute(
    `SELECT id, business_name, email, currency_code, timezone, date_format
     FROM business_accounts WHERE id = ? LIMIT 1`,
    [businessAccountId]
  );
  return rows[0] || null;
}

async function updatePreferences({ businessAccountId, businessName, currencyCode, timezone, dateFormat }) {
  const [result] = await db.execute(
    `UPDATE business_accounts
     SET business_name = ?, currency_code = ?, timezone = ?, date_format = ?
     WHERE id = ?`,
    [businessName, currencyCode, timezone, dateFormat, businessAccountId]
  );
  return result.affectedRows > 0;
}

async function getPasswordHash({ businessAccountId }) {
  const [rows] = await db.execute("SELECT password_hash FROM business_accounts WHERE id = ? LIMIT 1", [businessAccountId]);
  return rows[0]?.password_hash || null;
}

async function updatePassword({ businessAccountId, passwordHash }) {
  const [result] = await db.execute("UPDATE business_accounts SET password_hash = ? WHERE id = ?", [passwordHash, businessAccountId]);
  return result.affectedRows > 0;
}

module.exports = { getSettings, updatePreferences, getPasswordHash, updatePassword };
