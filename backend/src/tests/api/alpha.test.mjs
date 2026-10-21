import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";
import routesModule from "../../../routes/alphaRoutes.js";
import serviceModule from "../../services/alphaService.js";
import clientModule from "../../services/engineClient.js";

const { createAlphaRouter } = routesModule;
const { createAlphaService } = serviceModule;
const { createEngineClient } = clientModule;

function fakeRepo() {
  const files = [{ id: 1, name: "a.csv", path: "/up/a.csv", owner: 7 }, { id: 2, name: "b.csv", path: "/up/b.csv", owner: 8 }];
  const analyses = {};
  return {
    files, analyses,
    addFile: vi.fn(async (f) => ({ id: 9, name: f.originalName })),
    listFiles: vi.fn(async (o) => files.filter((f) => f.owner === o)),
    getFiles: vi.fn(async (o, ids) => files.filter((f) => f.owner === o && ids.includes(f.id))),
    deleteFile: vi.fn(async (o, id) => files.find((f) => f.owner === o && f.id === id) || null),
    createAnalysis: vi.fn(async (a) => { analyses[a.id] = { id: a.id, owner: a.businessAccountId, status: "queued", stage: "", progress: 0 }; }),
    getAnalysis: vi.fn(async (o, id) => (analyses[id]?.owner === o ? analyses[id] : null)),
    listAnalyses: vi.fn(async () => []),
    updateAnalysis: vi.fn(async (o, id, patch) => { Object.assign(analyses[id], patch); }),
    getReport: vi.fn(async (o, id) => (analyses[id]?.owner === o && analyses[id].report) || null),
    saveFeedback: vi.fn(async () => {}), listPatternPreferences: vi.fn(async () => [{ patternKey: "net_sales|region", verdict: "not_useful" }]), listFeedback: vi.fn(async () => []),
    saveAnswer: vi.fn(async () => {}), listAnswers: vi.fn(async () => []),
    listMemory: vi.fn(async () => ({ ship_mode: "channel" })), saveMemory: vi.fn(async () => {}),
    saveQuestion: vi.fn(async () => {}), listQuestions: vi.fn(async () => [{ question: "q1", result: { answer: "a1" } }])
  };
}

function build({ repo = fakeRepo(), engine } = {}) {
  engine = engine || { read: vi.fn(async () => ({ files: [], links: [] })), analyze: vi.fn(async () => ({ accepted: true })), job: vi.fn(), report: vi.fn() };
  const removeFile = vi.fn(async () => {});
  const service = createAlphaService({ repository: repo, engine, removeFile });
  const upload = { array: () => (req, res, next) => { req.files = req.headers["x-has-file"] ? [{ originalname: "a.csv", path: "/up/x.csv", size: 5 }] : []; next(); } };
  const app = express();
  app.use(express.json());
  app.use((req, res, next) => { req.user = { id: 7 }; next(); });
  app.use("/api/alpha", createAlphaRouter({ service, upload }));
  app.use((e, req, res, next) => res.status(e.status || 500).json({ message: e.message }));
  return { app, repo, engine, removeFile };
}

describe("alpha API", () => {
  it("registers uploads and refuses an empty upload", async () => {
    const { app, repo } = build();
    expect((await request(app).post("/api/alpha/files")).status).toBe(400);
    const r = await request(app).post("/api/alpha/files").set("x-has-file", "1");
    expect(r.status).toBe(201);
    expect(repo.addFile).toHaveBeenCalledWith(expect.objectContaining({ businessAccountId: 7, originalName: "a.csv" }));
  });

  it("only lets an owner use and delete their own files", async () => {
    const { app, engine, removeFile } = build();
    expect((await request(app).post("/api/alpha/read").send({ fileIds: [2] })).status).toBe(404);
    expect((await request(app).post("/api/alpha/read").send({ fileIds: [] })).status).toBe(400);
    expect((await request(app).post("/api/alpha/read").send({ fileIds: [1] })).status).toBe(200);
    expect(engine.read).toHaveBeenCalledWith(expect.objectContaining({ files: [{ id: 1, name: "a.csv", path: "/up/a.csv" }] }));
    expect((await request(app).delete("/api/alpha/files/2")).status).toBe(404);
    expect((await request(app).delete("/api/alpha/files/1")).status).toBe(200);
    expect(removeFile).toHaveBeenCalledWith("/up/a.csv");
  });

  it("starts an analysis, follows progress, stores the finished report", async () => {
    const { app, repo, engine } = build();
    const start = await request(app).post("/api/alpha/analyses").send({ fileIds: [1], confirmations: { links: {} } });
    expect(start.status).toBe(202);
    const id = start.body.id;
    engine.job.mockResolvedValueOnce({ status: "running", stage: "Looking for changes", progress: 40 });
    let s = await request(app).get(`/api/alpha/analyses/${id}`);
    expect(s.body.analysis).toMatchObject({ status: "running", progress: 40 });
    expect((await request(app).get(`/api/alpha/analyses/${id}/report`)).status).toBe(404);
    engine.job.mockResolvedValueOnce({ status: "done", progress: 100 });
    engine.report.mockResolvedValueOnce({ briefing: { headline: "x" } });
    s = await request(app).get(`/api/alpha/analyses/${id}`);
    expect(s.body.analysis.status).toBe("done");
    const rep = await request(app).get(`/api/alpha/analyses/${id}/report`);
    expect(rep.body.report.briefing.headline).toBe("x");
    expect(rep.body.report.owner).toEqual({ feedback: [], answers: [] });
    expect(repo.analyses[id].status).toBe("done");
  });

  it("hides other owners' analyses and marks a lost job as failed", async () => {
    const { app, repo, engine } = build();
    const { body } = await request(app).post("/api/alpha/analyses").send({ fileIds: [1] });
    repo.analyses[body.id].owner = 99;
    expect((await request(app).get(`/api/alpha/analyses/${body.id}`)).status).toBe(404);
    repo.analyses[body.id].owner = 7;
    engine.job.mockResolvedValueOnce({ status: "unknown" });
    const s = await request(app).get(`/api/alpha/analyses/${body.id}`);
    expect(s.body.analysis.status).toBe("failed");
  });

  it("reports an unreachable engine as a clear failure and records it", async () => {
    const engine = createEngineClient({ fetchImpl: async () => { throw new Error("ECONNREFUSED"); } });
    const { app, repo } = build({ engine });
    const r = await request(app).post("/api/alpha/analyses").send({ fileIds: [1] });
    expect(r.status).toBe(503);
    expect(r.body.message).toMatch(/not reachable/);
    expect(Object.values(repo.analyses)[0].status).toBe("failed");
  });

  it("validates feedback and answers", async () => {
    const { app, repo } = build();
    const { body } = await request(app).post("/api/alpha/analyses").send({ fileIds: [1] });
    const base = `/api/alpha/analyses/${body.id}`;
    expect((await request(app).post(`${base}/feedback`).send({ findingId: "f1", verdict: "maybe" })).status).toBe(400);
    expect((await request(app).post(`${base}/feedback`).send({ findingId: "f1", verdict: "useful" })).status).toBe(200);
    expect(repo.saveFeedback).toHaveBeenCalledWith(expect.objectContaining({ businessAccountId: 7, findingId: "f1" }));
    expect((await request(app).post(`${base}/answers`).send({ questionId: "q", answer: "  " })).status).toBe(400);
    expect((await request(app).post(`${base}/answers`).send({ questionId: "q", answer: "price rise" })).status).toBe(200);
    expect((await request(app).post("/api/alpha/analyses/nope/feedback").send({ findingId: "f", verdict: "useful" })).status).toBe(404);
  });

  it("asks a question only on a finished analysis owned by the caller", async () => {
    const { app, repo, engine } = build();
    engine.ask = vi.fn(async () => ({ answer: "There are 5 rows.", verified: true }));
    const { body } = await request(app).post("/api/alpha/analyses").send({ fileIds: [1] });
    const url = `/api/alpha/analyses/${body.id}/ask`;
    expect((await request(app).post(url).send({ question: "ab" })).status).toBe(400);
    expect((await request(app).post(url).send({ question: "How many rows?" })).status).toBe(409);
    repo.analyses[body.id].status = "done";
    const r = await request(app).post(url).send({ question: "How many rows?" });
    expect(r.body.result.answer).toBe("There are 5 rows.");
    expect(engine.ask).toHaveBeenCalledWith({ analysis_id: body.id, question: "How many rows?", history: [{ q: "q1", a: "a1" }] });
    expect(repo.saveQuestion).toHaveBeenCalledWith(expect.objectContaining({ question: "How many rows?" }));
    expect((await request(app).post("/api/alpha/analyses/nope/ask").send({ question: "How many rows?" })).status).toBe(404);
  });

  it("passes remembered preferences to the engine and stores the kind of finding when feedback is given", async () => {
    const { app, repo, engine } = build();
    const { body } = await request(app).post("/api/alpha/analyses").send({ fileIds: [1] });
    expect(engine.analyze).toHaveBeenCalledWith(expect.objectContaining({ preferences: { "net_sales|region": "not_useful" } }));
    repo.analyses[body.id].report = { insights: { items: [{ id: "f1", pattern: "net_sales|region" }] } };
    repo.analyses[body.id].status = "done";
    await request(app).post(`/api/alpha/analyses/${body.id}/feedback`).send({ findingId: "f1", verdict: "useful" });
    expect(repo.saveFeedback).toHaveBeenCalledWith(expect.objectContaining({ patternKey: "net_sales|region", verdict: "useful" }));
  });

  it("remembers confirmed column meanings and sends them to the engine", async () => {
    const { app, repo, engine } = build();
    await request(app).post("/api/alpha/analyses").send({ fileIds: [1], confirmations: { concepts: { "a.csv::QtyOnHand": "stock_level", "a.csv::x": "BAD VALUE!" } } });
    expect(repo.saveMemory).toHaveBeenCalledWith(7, [["qty_on_hand", "stock_level"]]);
    expect(engine.analyze).toHaveBeenCalledWith(expect.objectContaining({ memory: { ship_mode: "channel" } }));
    await request(app).post("/api/alpha/read").send({ fileIds: [1] });
    expect(engine.read).toHaveBeenCalledWith(expect.objectContaining({ memory: { ship_mode: "channel" } }));
  });

  it("exports a finished report as pdf or xlsx and refuses other formats", async () => {
    const { app, repo, engine } = build();
    engine.exportFile = vi.fn(async () => Buffer.from("%PDF-fake"));
    const { body } = await request(app).post("/api/alpha/analyses").send({ fileIds: [1] });
    repo.analyses[body.id].report = { briefing: {} }; repo.analyses[body.id].status = "done";
    const r = await request(app).get(`/api/alpha/analyses/${body.id}/export?format=pdf`);
    expect(r.status).toBe(200);
    expect(r.headers["content-type"]).toMatch(/pdf/);
    expect(r.headers["content-disposition"]).toMatch(/alpha-report\.pdf/);
    expect((await request(app).get(`/api/alpha/analyses/${body.id}/export?format=doc`)).status).toBe(400);
  });

  it("sends the engine key and maps engine errors", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 400, json: async () => ({ detail: "file is outside the upload folder" }) }));
    const client = createEngineClient({ baseUrl: "http://e", apiKey: "k", fetchImpl });
    await expect(client.read({})).rejects.toMatchObject({ status: 400, message: "file is outside the upload folder" });
    expect(fetchImpl.mock.calls[0][1].headers["x-engine-key"]).toBe("k");
  });
});
