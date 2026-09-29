import { describe, expect, it } from "vitest";
import { makeQueueItems, validateFile } from "./uploadQueue";

function file(name, size = 100) {
  return { name, size };
}

describe("upload queue", () => {
  it("accepts supported file extensions without case sensitivity", () => {
    expect(validateFile(file("sales.CSV"))).toBe("");
    expect(validateFile(file("inventory.xlsx"))).toBe("");
  });

  it("marks invalid files independently", () => {
    const items = makeQueueItems([
      file("sales.csv"),
      file("notes.txt"),
      file("large.xlsx", 10 * 1024 * 1024 + 1)
    ], 123);

    expect(items.map((item) => item.status)).toEqual(["queued", "invalid", "invalid"]);
    expect(items[1].error).toMatch(/unsupported/i);
    expect(items[2].error).toMatch(/10 MB/i);
  });

  it("caps one batch at ten files", () => {
    const items = makeQueueItems(
      Array.from({ length: 12 }, (_, index) => file(`sales-${index}.csv`)),
      123
    );
    expect(items).toHaveLength(10);
  });
});
