import { describe, expect, it } from "vitest";
import validationModule from "../../engine/validation/validateRows.js";

const { validateRows } = validationModule;
const mappings = [
  { originalHeader: "Date", field: "order_date" },
  { originalHeader: "Item", field: "product_name" },
  { originalHeader: "Qty", field: "quantity" },
  { originalHeader: "Price", field: "unit_price" },
  { originalHeader: "Email", field: "customer_email" },
  { originalHeader: "Status", field: "status" }
];

describe("validation engine", () => {
  it("repairs parseable values while keeping raw evidence", () => {
    const result = validateRows({
      datasetType: "sales",
      mappings,
      rawRows: [
        { sourceRowNumber: 2, rawData: { Date: "13/09/2026", Item: " Helmet ", Qty: "2", Price: "₹1,200.50", Email: "a@example.com", Status: "Complete" } },
        { sourceRowNumber: 3, rawData: { Date: "01/09/2026", Item: "Gloves", Qty: 1, Price: 300, Email: "bad-email", Status: "pending" } }
      ]
    });

    expect(result.rows[0]).toMatchObject({
      status: "repaired",
      canonical: { order_date: "2026-09-13", quantity: 2, unit_price: 1200.5, status: "completed" }
    });
    expect(result.rows[0].rawValues.Price).toBe("₹1,200.50");
    expect(result.rows[1].issues.some((issue) => issue.code === "INVALID_EMAIL")).toBe(true);
    expect(result.summary.skippedRows).toBe(0);
  });

  it("never guesses an unresolved numeric date order", () => {
    const result = validateRows({
      datasetType: "sales",
      mappings,
      rawRows: [{ sourceRowNumber: 2, rawData: { Date: "01/09/2026", Item: "Helmet", Qty: 1, Price: 100 } }]
    });

    expect(result.rows[0].status).toBe("skipped");
    expect(result.rows[0].issues[0].code).toBe("AMBIGUOUS_DATE_FORMAT");
  });

  it("skips invalid, impossible, and duplicate rows without rejecting valid rows", () => {
    const raw = { Date: "2026-09-01", Item: "Helmet", Qty: 2, Price: 100 };
    const result = validateRows({
      datasetType: "sales",
      mappings,
      rawRows: [
        { sourceRowNumber: 2, rawData: raw },
        { sourceRowNumber: 3, rawData: raw },
        { sourceRowNumber: 4, rawData: { ...raw, Qty: -1, Item: "Gloves" } },
        { sourceRowNumber: 5, rawData: { ...raw, Qty: "text", Item: "Jacket" } }
      ]
    });

    expect(result.summary).toMatchObject({ totalRows: 4, skippedRows: 3 });
    expect(result.issues.map((issue) => issue.code)).toEqual(expect.arrayContaining([
      "DUPLICATE_ROW", "NEGATIVE_QUANTITY", "INVALID_NUMBER"
    ]));
  });
});
