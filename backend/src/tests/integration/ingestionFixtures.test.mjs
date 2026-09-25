import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import datasetServiceModule from "../../services/datasetService.js";
import fileProcessingModule from "../../../services/fileprocessingservices.js";
import datasetTypeModule from "../../engine/ingestion/detectDatasetType.js";

const { createDatasetService } = datasetServiceModule;
const { processFile } = fileProcessingModule;
const { detectDatasetType } = datasetTypeModule;
const fixtureDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../fixtures"
);
const expected = JSON.parse(
  fs.readFileSync(path.join(fixtureDirectory, "ingestion_expected.json"), "utf8")
);

function fixtureFile(fileName) {
  const filePath = path.join(fixtureDirectory, fileName);
  return {
    originalname: fileName,
    path: filePath,
    size: fs.statSync(filePath).size
  };
}

describe("Module 2 fixture integration", () => {
  it.each([
    ["sales_clean.csv", "sales_clean"],
    ["inventory.xlsx", "inventory"],
    ["customers.csv", "customers"],
    ["suppliers.xlsx", "suppliers"]
  ])("parses and classifies %s", (fileName, expectationName) => {
    const result = processFile(fixtureFile(fileName));
    const expectation = expected[expectationName];

    expect(result.rows).toHaveLength(expectation.rows);
    expect(result.headers).toHaveLength(expectation.columns);
    if (expectation.type) {
      expect(detectDatasetType(result.headers, result.rows).type).toBe(expectation.type);
    }
    if (expectation.first_sheet) {
      expect(result.sheetName).toBe(expectation.first_sheet);
      expect(result.workbook.ignoredSheetCount).toBe(expectation.ignored_sheets);
    }
  });

  it("runs a real fixture through hash, parse, profile, classify, and persistence handoff", async () => {
    const db = { execute: vi.fn(async () => [[]]) };
    const saveIngestion = vi.fn(async () => 501);
    const service = createDatasetService({ db, saveIngestion });

    const result = await service.ingestDataset({
      businessAccountId: 7,
      file: fixtureFile("sales_clean.csv")
    });

    expect(result.ingestionId).toBe(501);
    expect(result.sourceFile.fileHash).toMatch(/^[a-f0-9]{64}$/);
    expect(result.dataset.rows).toHaveLength(300);
    expect(result.dataset.type.type).toBe("sales");
    expect(result.processing.status).toBe("completed");
    expect(saveIngestion).toHaveBeenCalledWith(expect.objectContaining({
      businessAccountId: 7,
      datasetType: "sales",
      dataset: expect.objectContaining({
        sourceRowNumbers: expect.arrayContaining([2, 301])
      })
    }));
  });

  it("stops duplicate content before parsing or persistence", async () => {
    const db = { execute: vi.fn(async () => [[{
      id: 88,
      original_file_name: "previous.csv",
      created_at: "2026-09-24"
    }]]) };
    const processFileSpy = vi.fn();
    const saveIngestion = vi.fn();
    const service = createDatasetService({
      db,
      processFile: processFileSpy,
      saveIngestion
    });

    await expect(service.ingestDataset({
      businessAccountId: 7,
      file: fixtureFile("sales_clean.csv")
    })).rejects.toMatchObject({ code: "DUPLICATE_DATASET", status: 409 });

    expect(processFileSpy).not.toHaveBeenCalled();
    expect(saveIngestion).not.toHaveBeenCalled();
  });
});
