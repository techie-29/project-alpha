import { describe, expect, it, vi } from "vitest";
import batchServiceModule from "../../services/uploadBatchService.js";

const { createBatchProcessor } = batchServiceModule;

function createRepository() {
  const state = { completed: 0, failed: 0, results: [] };
  return {
    state,
    createBatch: vi.fn(async () => 41),
    markItemProcessing: vi.fn(async () => {}),
    recordItemResult: vi.fn(async (result) => {
      state.results.push(result);
      if (result.error) state.failed += 1;
      else state.completed += 1;
    }),
    finishBatch: vi.fn(async () => ({
      id: 41,
      status: state.failed === 0 ? "completed" : state.completed === 0 ? "failed" : "partial",
      totalFiles: state.completed + state.failed,
      completedFiles: state.completed,
      failedFiles: state.failed
    }))
  };
}

describe("upload batch service", () => {
  it("continues processing after one file fails", async () => {
    const repository = createRepository();
    const ingest = vi.fn(async ({ file }) => {
      if (file.originalname === "duplicate.csv") {
        const error = new Error("This exact file has already been uploaded");
        error.status = 409;
        error.code = "DUPLICATE_DATASET";
        throw error;
      }
      return { ingestionId: file.originalname === "sales.csv" ? 11 : 12 };
    });
    const processBatch = createBatchProcessor({ ingest, repository });

    const result = await processBatch({
      businessAccountId: 7,
      files: [
        { originalname: "sales.csv" },
        { originalname: "duplicate.csv" },
        { originalname: "inventory.xlsx" }
      ]
    });

    expect(ingest).toHaveBeenCalledTimes(3);
    expect(result.batch).toMatchObject({
      status: "partial",
      completedFiles: 2,
      failedFiles: 1
    });
    expect(result.items.map((item) => item.status))
      .toEqual(["completed", "failed", "completed"]);
    expect(result.items[1].error.code).toBe("DUPLICATE_DATASET");
  });
});
