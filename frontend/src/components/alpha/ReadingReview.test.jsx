import React from "react";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ReadingReview from "./ReadingReview";

const table = (name) => ({ name, role: "transactions", rows: 10, role_reason: "", warnings: [], notes: [`Sheet '${name.split(" › ")[1]}' of Book.xlsx.`], columns: [] });
const reading = {
  files: [table("Book.xlsx › Orders"), table("Book.xlsx › Returns"), { ...table("Book.xlsx › X"), name: "sales.csv", notes: [] }],
  links: [], concepts: [], ai_review: null
};
globalThis.React = React;                // the test runner compiles JSX the classic way
const empty = { concepts: {}, links: {}, rowOrder: {}, dateOrder: {}, timeCol: {} };

describe("ReadingReview", () => {
  it("groups the sheets of one workbook under the file name and says how many tables came from how many files", () => {
    const html = renderToStaticMarkup(<ReadingReview reading={reading} choices={empty} setChoices={() => {}}/>);
    expect(html).toContain("2 files → 3 tables");
    expect(html).toContain("2 sheets: Orders, Returns");
    expect(html).toContain("sheet of Book.xlsx");
    expect(html).toContain("sales.csv");
    expect(html).not.toContain("Sheet &#x27;Orders&#x27; of Book.xlsx.");     // the heading already says it
  });
});
