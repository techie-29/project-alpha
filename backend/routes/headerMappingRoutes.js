const express = require("express");
const {
  getMappingWorkspace,
  confirmHeaderMapping
} = require("../services/headerMappingService");

function createHeaderMappingRouter({
  getWorkspace = getMappingWorkspace,
  confirmMapping = confirmHeaderMapping
} = {}) {
  const router = express.Router();

  async function sendWorkspace(req, res, next) {
    try {
      const data = await getWorkspace({
        businessAccountId: req.user.id,
        ingestionId: req.params.ingestionId
      });
      return res.json({
        success: true,
        message: data.reusedSavedMapping
          ? "A saved mapping template was applied"
          : "Header mapping suggestions are ready",
        data
      });
    } catch (error) {
      next(error);
    }
  }

  router.get("/:ingestionId", sendWorkspace);

  // Backward-compatible alias for the original Module 3 endpoint.
  router.post("/:ingestionId", sendWorkspace);

  router.put("/:ingestionId", async (req, res, next) => {
    try {
      const data = await confirmMapping({
        businessAccountId: req.user.id,
        ingestionId: req.params.ingestionId,
        mappings: req.body.mappings,
        saveTemplate: req.body.saveTemplate !== false
      });
      return res.json({
        success: true,
        message: "Header mapping confirmed successfully",
        data
      });
    } catch (error) {
      next(error);
    }
  });

  return router;
}

module.exports = createHeaderMappingRouter();
module.exports.createHeaderMappingRouter = createHeaderMappingRouter;
