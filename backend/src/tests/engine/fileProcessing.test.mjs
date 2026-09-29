import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import XLSX from "xlsx";
import fileProcessingModule from "../../../services/fileprocessingservices.js";

const { processFile } = fileProcessingModule;
const temporaryFiles = [];

function temporaryPath(extension) {
  const filePath = path.join(
    os.tmpdir(),
    `alpha-ingestion-${process.pid}-${Date.now()}-${temporaryFiles.length}${extension}`
  );
  temporaryFiles.push(filePath);
  return filePath;
}

afterEach(() => {
  temporaryFiles.splice(0).forEach((filePath) => {
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
  });
});

describe("file processing integration", () => {
  it("parses a BOM CSV and preserves original source row numbers", () => {
    const filePath = temporaryPath(".csv");
    fs.writeFileSync(filePath, "\uFEFFProduct,Qty\nHelmet,2\n\nGloves,3\n", "utf8");

    const result = processFile({ originalname: "sales.csv", path: filePath });

    expect(result.headers).toEqual(["Product", "Qty"]);
    expect(result.rows).toHaveLength(2);
    expect(result.sourceRowNumbers).toEqual([2, 4]);
  });

  it("uses only the first sheet and repairs a two-level merged header", () => {
    const filePath = temporaryPath(".xlsx");
    const workbook = XLSX.utils.book_new();
    const firstSheet = XLSX.utils.aoa_to_sheet([
      ["Order", null, "Product"],
      ["ID", "Date", null],
      ["A-1", new Date(Date.UTC(2026, 8, 1)), "Helmet"]
    ], { cellDates: true });
    firstSheet["!merges"] = [
      { s: { r: 0, c: 0 }, e: { r: 0, c: 1 } },
      { s: { r: 0, c: 2 }, e: { r: 1, c: 2 } }
    ];
    XLSX.utils.book_append_sheet(workbook, firstSheet, "Sales");
    XLSX.utils.book_append_sheet(
      workbook,
      XLSX.utils.aoa_to_sheet([["Ignored"], ["row"]]),
      "Archive"
    );
    XLSX.writeFile(workbook, filePath, { cellDates: true });

    const result = processFile({ originalname: "sales.xlsx", path: filePath });

    expect(result.sheetName).toBe("Sales");
    expect(result.headers).toEqual(["Order ID", "Order Date", "Product"]);
    expect(result.rows[0]["Order Date"]).toBe("2026-09-01");
    expect(result.sourceRowNumbers).toEqual([3]);
    expect(result.workbook).toMatchObject({
      sheetCount: 2,
      ignoredSheetCount: 1,
      mergedRangeCount: 2
    });
    expect(result.warnings).toContain("Only the first worksheet was processed; 1 additional worksheet was ignored.");
  });
});
