const express = require("express");
const service = require("../src/services/settingsService");

function createSettingsRouter({ get = service.get, update = service.update, changePassword = service.changePassword } = {}) {
  const router = express.Router();
  router.get("/", async (req, res, next) => {
    try { return res.json({ success: true, data: await get({ businessAccountId: req.user.id }) }); } catch (error) { next(error); }
  });
  router.patch("/", async (req, res, next) => {
    try { return res.json({ success: true, message: "Business settings updated", data: await update({ businessAccountId: req.user.id, body: req.body }) }); } catch (error) { next(error); }
  });
  router.patch("/password", async (req, res, next) => {
    try { return res.json({ success: true, message: "Password updated", data: await changePassword({ businessAccountId: req.user.id, body: req.body }) }); } catch (error) { next(error); }
  });
  return router;
}

module.exports = createSettingsRouter();
module.exports.createSettingsRouter = createSettingsRouter;
