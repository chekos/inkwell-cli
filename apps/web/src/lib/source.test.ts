import { describe, expect, it } from "vitest";

import { detectSourceKind, sourceHost, sourceKindLabel } from "@/lib/source";

describe("source helpers", () => {
  it("detects common Inkwell source kinds", () => {
    expect(detectSourceKind("https://youtu.be/abc")).toBe("youtube");
    expect(detectSourceKind("https://example.com/feed.xml")).toBe("rss");
    expect(detectSourceKind("https://cdn.example.com/audio.mp3")).toBe("media");
    expect(detectSourceKind("https://example.com/story")).toBe("web");
  });

  it("formats source labels and hosts for compact UI", () => {
    expect(sourceKindLabel("youtube")).toBe("YouTube");
    expect(sourceHost("https://www.example.com/feed.xml")).toBe("example.com");
  });
});
