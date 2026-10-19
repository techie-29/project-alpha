const crypto = require("crypto");
const fs = require("fs");
const defaultRepository = require("./alphaRepository");
const { createEngineClient } = require("./engineClient");

function httpError(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function createAlphaService({ repository = defaultRepository, engine = createEngineClient(), removeFile = (p) => fs.promises.unlink(p).catch(() => {}) } = {}) {
  async function filesFor(businessAccountId, fileIds) {
    const ids = [...new Set((fileIds || []).map(Number).filter(Number.isInteger))];
    if (!ids.length) throw httpError(400, "Choose at least one file");
    const files = await repository.getFiles(businessAccountId, ids);
    if (files.length !== ids.length) throw httpError(404, "One of the files was not found");
    return files.map((f) => ({ id: f.id, name: f.name, path: f.path }));
  }

  return {
    async registerUploads(businessAccountId, uploaded) {
      const out = [];
      for (const f of uploaded) {
        out.push(await repository.addFile({ businessAccountId, originalName: f.originalname, storedPath: f.path, sizeBytes: f.size }));
      }
      return out;
    },
    listFiles: (businessAccountId) => repository.listFiles(businessAccountId),
    async deleteFile(businessAccountId, id) {
      const row = await repository.deleteFile(businessAccountId, id);
      if (!row) throw httpError(404, "File not found");
      await removeFile(row.path);
    },
    async read(businessAccountId, { fileIds, confirmations }) {
      const files = await filesFor(businessAccountId, fileIds);
      return engine.read({ files, confirmations: confirmations || {}, use_ai: true });
    },
    async start(businessAccountId, { fileIds, confirmations }) {
      const files = await filesFor(businessAccountId, fileIds);
      const id = crypto.randomUUID();
      await repository.createAnalysis({ id, businessAccountId, fileIds: files.map((f) => f.id), confirmations });
      try {
        await engine.analyze({ analysis_id: id, files, confirmations: confirmations || {}, use_ai: true });
      } catch (error) {
        await repository.updateAnalysis(businessAccountId, id, { status: "failed", error: error.message.slice(0, 480) });
        throw error;
      }
      await repository.updateAnalysis(businessAccountId, id, { status: "running", stage: "Starting", progress: 1 });
      return { id };
    },
    /** Status check; when the engine finished, store the report so it survives engine restarts. */
    async status(businessAccountId, id) {
      const a = await repository.getAnalysis(businessAccountId, id);
      if (!a) throw httpError(404, "Analysis not found");
      if (a.status === "done" || a.status === "failed") return pick(a);
      let job;
      try { job = await engine.job(id); } catch (error) { return { ...pick(a), engineMessage: error.message }; }
      if (job.status === "done") {
        const report = await engine.report(id);
        await repository.updateAnalysis(businessAccountId, id, { status: "done", stage: "Done", progress: 100, report });
        return { ...pick(a), status: "done", stage: "Done", progress: 100 };
      }
      if (job.status === "failed") {
        await repository.updateAnalysis(businessAccountId, id, { status: "failed", error: job.error || "The analysis stopped" });
        return { ...pick(a), status: "failed", error: job.error };
      }
      if (job.status === "unknown") {
        await repository.updateAnalysis(businessAccountId, id, { status: "failed", error: "The engine lost this job (it may have restarted). Please run it again." });
        return { ...pick(a), status: "failed", error: "The engine lost this job (it may have restarted). Please run it again." };
      }
      await repository.updateAnalysis(businessAccountId, id, { stage: job.stage, progress: job.progress });
      return { ...pick(a), status: "running", stage: job.stage, progress: job.progress };
    },
    list: (businessAccountId) => repository.listAnalyses(businessAccountId),
    async report(businessAccountId, id) {
      const report = await repository.getReport(businessAccountId, id);
      if (!report) throw httpError(404, "The report is not ready");
      const [feedback, answers] = await Promise.all([repository.listFeedback(businessAccountId, id), repository.listAnswers(businessAccountId, id)]);
      return { ...report, owner: { feedback, answers } };
    },
    async feedback(businessAccountId, id, { findingId, verdict, note }) {
      if (!["useful", "not_useful"].includes(verdict)) throw httpError(400, "verdict must be useful or not_useful");
      if (!findingId || typeof findingId !== "string") throw httpError(400, "findingId is required");
      if (!(await repository.getAnalysis(businessAccountId, id))) throw httpError(404, "Analysis not found");
      await repository.saveFeedback({ businessAccountId, analysisId: id, findingId: findingId.slice(0, 80), verdict, note: note ? String(note).slice(0, 500) : null });
    },
    async ask(businessAccountId, id, { question }) {
      if (typeof question !== "string" || question.trim().length < 3) throw httpError(400, "Type a question first");
      const a = await repository.getAnalysis(businessAccountId, id);
      if (!a) throw httpError(404, "Analysis not found");
      if (a.status !== "done") throw httpError(409, "The analysis is not finished yet");
      return engine.ask({ analysis_id: id, question: question.trim().slice(0, 500) });
    },
    async answer(businessAccountId, id, { questionId, answer }) {
      if (!questionId || typeof answer !== "string" || !answer.trim()) throw httpError(400, "questionId and answer are required");
      if (!(await repository.getAnalysis(businessAccountId, id))) throw httpError(404, "Analysis not found");
      await repository.saveAnswer({ businessAccountId, analysisId: id, questionId: String(questionId).slice(0, 80), answer: answer.trim().slice(0, 1000) });
    }
  };
}

function pick(a) {
  return { id: a.id, status: a.status, stage: a.stage, progress: a.progress, error: a.error, createdAt: a.createdAt, finishedAt: a.finishedAt };
}

module.exports = { createAlphaService };
