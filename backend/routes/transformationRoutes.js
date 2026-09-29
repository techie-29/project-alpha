const express = require("express");
const {
  runTransformation: defaultRunTransformation,
  getTransformation: defaultGetTransformation
} = require("../src/services/transformationService");

function createTransformationRouter({
  runTransformation = defaultRunTransformation,
  getTransformation = defaultGetTransformation
} = {}) {
  const router = express.Router();
  router.get("/:ingestionId", async (req, res, next) => {
    try {
      const data = await getTransformation({ businessAccountId: req.user.id, ingestionId: req.params.ingestionId });
      return res.json({ success: true, data });
    } catch (error) { next(error); }
  });
  router.post("/:ingestionId/run", async (req, res, next) => {
    try {
      const data = await runTransformation({ businessAccountId: req.user.id, ingestionId: req.params.ingestionId });
      return res.json({ success: true, message: "Transformation and structured storage completed", data });
    } catch (error) { next(error); }
  });
  return router;
}

module.exports = createTransformationRouter();
module.exports.createTransformationRouter = createTransformationRouter;
