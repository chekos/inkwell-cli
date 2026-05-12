import { describe, expect, it } from "vitest";

import { extractMarkdownHeadings, filenameFromTitle, slugifyHeading } from "@/lib/markdown";

describe("markdown helpers", () => {
  it("extracts stable section links", () => {
    expect(extractMarkdownHeadings("# Summary\n\n## Key Concepts\n\n### Active learning")).toEqual([
      { id: "summary", text: "Summary", level: 1 },
      { id: "key-concepts", text: "Key Concepts", level: 2 },
      { id: "active-learning", text: "Active learning", level: 3 },
    ]);
  });

  it("creates readable markdown filenames", () => {
    expect(slugifyHeading("My Great Episode!")).toBe("my-great-episode");
    expect(filenameFromTitle("My Great Episode!")).toBe("my-great-episode.md");
  });
});
