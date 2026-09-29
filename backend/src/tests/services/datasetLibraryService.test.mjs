import { describe, expect, it, vi } from "vitest";
import serviceModule from "../../services/datasetLibraryService.js";

const { createDatasetLibraryService, overlapWarnings } = serviceModule;

describe("dataset library service", () => {
  it("adds same-type date overlap warnings", () => {
    const result = overlapWarnings([
      { id: 1, filename: "a.csv", datasetType: "sales", dateFrom: "2026-09-01", dateTo: "2026-09-20" },
      { id: 2, filename: "b.csv", datasetType: "sales", dateFrom: "2026-09-15", dateTo: "2026-09-30" },
      { id: 3, filename: "stock.csv", datasetType: "inventory", dateFrom: "2026-09-01", dateTo: "2026-09-30" }
    ]);
    expect(result[0].overlapWarnings).toEqual([expect.objectContaining({ datasetId: 2 })]);
    expect(result[2].overlapWarnings).toEqual([]);
  });

  it("updates inclusion only within the repository tenant scope", async () => {
    const repository = { listDatasets: vi.fn(), getDataset: vi.fn(), setDatasetIncluded: vi.fn(async () => true) };
    const service = createDatasetLibraryService({ repository });
    const result = await service.setIncluded({ businessAccountId: 7, ingestionId: "12", included: false });
    expect(result).toEqual({ ingestionId: 12, included: false });
    expect(repository.setDatasetIncluded).toHaveBeenCalledWith({ businessAccountId: 7, ingestionId: "12", included: false });
  });

  it("preserves repeated-order evidence in library summaries", async () => {
    const repository = { listDatasets: vi.fn(async () => [{
      id: 12, original_file_name: "sales.csv", file_format: "csv", included: 1,
      row_count: 10, repeated_order_count: 3, validation_summary_json: null, quality_summary_json: null
    }]) };
    const service = createDatasetLibraryService({ repository });
    const result = await service.list({ businessAccountId: 7 });
    expect(result[0]).toMatchObject({ id: 12, repeatedOrderCount: 3 });
    expect(repository.listDatasets).toHaveBeenCalledWith({ businessAccountId: 7 });
  });

  it("rejects non-boolean inclusion values", async () => {
    const service = createDatasetLibraryService({ repository: {} });
    await expect(service.setIncluded({ businessAccountId: 7, ingestionId: 12, included: "false" })).rejects.toMatchObject({ status: 400 });
  });

  it("exports normalized rows as CSV and Excel", async () => {
    const repository = { loadExport: vi.fn(async () => ({ filename: "sales.csv", rows: [{ order_id: "A1", revenue: 200 }] })) };
    const service = createDatasetLibraryService({ repository });
    const csv = await service.exportDataset({ businessAccountId: 7, ingestionId: 12, type: "sales", format: "csv" });
    expect(csv.buffer.toString()).toContain('"order_id","revenue"');
    expect(csv.buffer.toString()).toContain('"A1","200"');
    const xlsx = await service.exportDataset({ businessAccountId: 7, ingestionId: 12, type: "sales", format: "xlsx" });
    expect(xlsx.buffer.subarray(0, 2).toString()).toBe("PK");
    expect(repository.loadExport).toHaveBeenCalledWith({ businessAccountId: 7, ingestionId: 12, type: "sales" });
  });
});
