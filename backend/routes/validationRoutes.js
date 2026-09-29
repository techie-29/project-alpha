const express = require("express");
const {
  runValidation: defaultRunValidation,
  getValidation: defaultGetValidation
} = require("../src/services/validationService");

function createValidationRouter({
  runValidation = defaultRunValidation,
  getValidation = defaultGetValidation
} = {}) {
  const router = express.Router();

  router.get("/:ingestionId", async (req, res, next) => {
    try {
      const data = await getValidation({
        businessAccountId: req.user.id,
        ingestionId: req.params.ingestionId
      });
      return res.json({ success: true, data });
    } catch (error) { next(error); }
  });

  router.post("/:ingestionId/run", async (req, res, next) => {
    try {
      const data = await runValidation({
        businessAccountId: req.user.id,
        ingestionId: req.params.ingestionId
      });
      return res.json({
        success: true,
        message: "Validation completed",
        data
      });
    } catch (error) { next(error); }
  });

  return router;
}

module.exports = createValidationRouter();
module.exports.createValidationRouter = createValidationRouter;
