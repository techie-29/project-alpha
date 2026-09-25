import express from "express";
import multer from "multer";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";
import uploadRoutesModule from "../../../routes/uploadroutes.js";

const { createUploadRouter } = uploadRoutesModule;

function testApp(dependencies) {
  const app = express();
  app.use((req, res, next) => {
    req.user = { id: 7, role: "user" };
    next();
  });
  app.use("/api/upload", createUploadRouter(dependencies));
  app.use((error, req, res, next) => {
    const status = error instanceof multer.MulterError ? 400 : error.status || 400;
    res.status(status).json({ success: false, code: error.code, message: error.message });
  });
  return app;
}

describe("upload API", () => {
  it("accepts a multi-file batch and returns per-file results", async () => {
    const processBatch = vi.fn(async ({ businessAccountId, files }) => ({
      batch: {
        id: 9,
        status: "partial",
        totalFiles: 2,
        completedFiles: 1,
        failedFiles: 1
      },
      items: [
        {
          fileIndex: 0,
          fileName: files[0].originalname,
          status: "completed",
          result: {
            ingestionId: 21,
            sourceFile: { fileName: files[0].originalname, format: "csv" },
            dataset: { headers: ["Product"], rows: [{ Product: "Helmet" }], profile: {} },
            processing: { status: "completed" }
          }
        },
        {
          fileIndex: 1,
          fileName: files[1].originalname,
          status: "failed",
          error: { code: "DUPLICATE_DATASET", message: "Already uploaded" }
        }
      ]
    }));
    const app = testApp({ processBatch, getBatch: vi.fn() });

    const response = await request(app)
      .post("/api/upload/batch")
      .attach("files", Buffer.from("Product\nHelmet\n"), "sales.csv")
      .attach("files", Buffer.from("Product\nHelmet\n"), "copy.csv");

    expect(response.status).toBe(200);
    expect(processBatch).toHaveBeenCalledWith(expect.objectContaining({
      businessAccountId: 7,
      files: expect.arrayContaining([
        expect.objectContaining({ originalname: "sales.csv" }),
        expect.objectContaining({ originalname: "copy.csv" })
      ])
    }));
    expect(response.body.data.batch.status).toBe("partial");
    expect(response.body.data.items[0].data.handoff.ingestionId).toBe(21);
    expect(response.body.data.items[1].error.code).toBe("DUPLICATE_DATASET");
  });

  it("rejects an empty batch before processing", async () => {
    const processBatch = vi.fn();
    const app = testApp({ processBatch, getBatch: vi.fn() });

    const response = await request(app).post("/api/upload/batch");

    expect(response.status).toBe(400);
    expect(response.body.code).toBe("EMPTY_BATCH");
    expect(processBatch).not.toHaveBeenCalled();
  });

  it("scopes batch lookup to the authenticated business", async () => {
    const getBatch = vi.fn(async () => null);
    const app = testApp({ processBatch: vi.fn(), getBatch });

    const response = await request(app).get("/api/upload/batches/99");

    expect(response.status).toBe(404);
    expect(getBatch).toHaveBeenCalledWith({ businessAccountId: 7, batchId: "99" });
  });
});
