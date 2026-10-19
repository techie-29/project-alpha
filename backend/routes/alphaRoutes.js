const express = require("express");
const alphaUpload = require("../middleware/alphaUpload");
const { createAlphaService } = require("../src/services/alphaService");

function createAlphaRouter({ service = createAlphaService(), upload = alphaUpload } = {}) {
  const router = express.Router();
  const wrap = (fn) => (req, res, next) => Promise.resolve(fn(req, res)).catch(next);
  const uid = (req) => req.user.id;

  router.post("/files", upload.array("files", alphaUpload.MAX_FILES), wrap(async (req, res) => {
    if (!req.files?.length) return res.status(400).json({ success: false, message: "Choose at least one file to upload" });
    res.status(201).json({ success: true, files: await service.registerUploads(uid(req), req.files) });
  }));
  router.get("/files", wrap(async (req, res) => res.json({ success: true, files: await service.listFiles(uid(req)) })));
  router.delete("/files/:id", wrap(async (req, res) => { await service.deleteFile(uid(req), Number(req.params.id)); res.json({ success: true }); }));

  router.post("/read", wrap(async (req, res) => res.json({ success: true, reading: await service.read(uid(req), req.body || {}) })));
  router.post("/analyses", wrap(async (req, res) => res.status(202).json({ success: true, ...(await service.start(uid(req), req.body || {})) })));
  router.get("/analyses", wrap(async (req, res) => res.json({ success: true, analyses: await service.list(uid(req)) })));
  router.get("/analyses/:id", wrap(async (req, res) => res.json({ success: true, analysis: await service.status(uid(req), req.params.id) })));
  router.get("/analyses/:id/report", wrap(async (req, res) => res.json({ success: true, report: await service.report(uid(req), req.params.id) })));
  router.get("/analyses/:id/export", wrap(async (req, res) => {
    const format = String(req.query.format || "pdf");
    const data = await service.export(uid(req), req.params.id, format);
    res.setHeader("Content-Type", format === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    res.setHeader("Content-Disposition", `attachment; filename="alpha-report.${format}"`);
    res.send(data);
  }));
  router.post("/analyses/:id/feedback", wrap(async (req, res) => { await service.feedback(uid(req), req.params.id, req.body || {}); res.json({ success: true }); }));
  router.post("/analyses/:id/ask", wrap(async (req, res) => res.json({ success: true, result: await service.ask(uid(req), req.params.id, req.body || {}) })));
  router.post("/analyses/:id/answers", wrap(async (req, res) => { await service.answer(uid(req), req.params.id, req.body || {}); res.json({ success: true }); }));

  return router;
}

module.exports = { createAlphaRouter };
