const express = require("express");
const service = require("../src/services/datasetLibraryService");

function createDatasetLibraryRouter({ list = service.list, get = service.get, setIncluded = service.setIncluded, exportDataset = service.exportDataset } = {}) {
  const router = express.Router();
  router.get("/", async (req, res, next) => {
    try { return res.json({ success: true, data: { datasets: await list({ businessAccountId: req.user.id }) } }); } catch (error) { next(error); }
  });
  router.get("/:ingestionId", async (req, res, next) => {
    try { return res.json({ success: true, data: await get({ businessAccountId: req.user.id, ingestionId: req.params.ingestionId }) }); } catch (error) { next(error); }
  });
  router.get("/:ingestionId/export", async (req, res, next) => {
    try {
      const file = await exportDataset({ businessAccountId: req.user.id, ingestionId: req.params.ingestionId, type: req.query.type || "sales", format: req.query.format || "csv" });
      res.setHeader("Content-Type", file.mime);
      res.setHeader("Content-Disposition", `attachment; filename="${file.filename}"`);
      return res.send(file.buffer);
    } catch (error) { next(error); }
  });
  router.patch("/:ingestionId/inclusion", async (req, res, next) => {
    try {
      const data = await setIncluded({ businessAccountId: req.user.id, ingestionId: req.params.ingestionId, included: req.body.included });
      return res.json({ success: true, message: data.included ? "Dataset included in analytics" : "Dataset excluded from analytics", data });
    } catch (error) { next(error); }
  });
  return router;
}

module.exports = createDatasetLibraryRouter();
module.exports.createDatasetLibraryRouter = createDatasetLibraryRouter;
