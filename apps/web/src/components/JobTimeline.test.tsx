import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { JobTimeline } from "@/components/JobTimeline";

describe("JobTimeline", () => {
  it("marks the active worker stage as current", () => {
    render(
      <JobTimeline
        status="running"
        stage="generating_notes"
        createdAt="2026-05-12T10:00:00Z"
        startedAt="2026-05-12T10:01:00Z"
      />,
    );

    expect(screen.getByRole("heading", { name: "Import timeline" })).toBeInTheDocument();
    expect(screen.getByText("Generating notes")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("Working")).toBeInTheDocument();
  });

  it("shows recovery copy when the worker fails", () => {
    render(
      <JobTimeline
        status="failed"
        stage="extracting_transcript"
        errorMessage="Transcript extraction failed."
        createdAt="2026-05-12T10:00:00Z"
      />,
    );

    expect(screen.getByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByText("Transcript extraction failed.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start another import" })).toHaveAttribute("href", "/app/new");
  });
});
