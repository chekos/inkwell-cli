import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LibraryList } from "./LibraryList";

const notes = [
  {
    id: "note-1",
    title: "Conversation with Jane",
    summary: "A useful summary about product research.",
    created_at: "2026-05-12T10:00:00Z",
    updated_at: "2026-05-12T11:00:00Z",
    source: {
      url: "https://www.youtube.com/watch?v=abc",
      title: "Video source",
      source_type: "youtube",
    },
  },
  {
    id: "note-2",
    title: "Old RSS episode",
    summary: null,
    created_at: "2025-12-12T10:00:00Z",
    updated_at: "2026-01-01T10:00:00Z",
    source: {
      url: "https://example.com/feed.xml",
      title: "RSS source",
      source_type: "rss",
    },
  },
];

describe("LibraryList", () => {
  it("filters notes by search text and source URL", () => {
    render(<LibraryList notes={notes} />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search library" }), {
      target: { value: "youtube" },
    });

    expect(screen.getByRole("heading", { name: "Conversation with Jane" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Old RSS episode" })).not.toBeInTheDocument();
  });

  it("filters to notes with summaries", () => {
    render(<LibraryList notes={notes} />);

    fireEvent.click(screen.getByRole("button", { name: "Summaries" }));

    expect(screen.getByRole("heading", { name: "Conversation with Jane" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Old RSS episode" })).not.toBeInTheDocument();
  });

  it("sorts notes by title", () => {
    render(<LibraryList notes={notes} />);

    fireEvent.change(screen.getByLabelText("Sort notes"), { target: { value: "title" } });

    const rows = screen.getAllByRole("link");
    expect(within(rows[0]).getByRole("heading", { name: "Conversation with Jane" })).toBeInTheDocument();
    expect(within(rows[1]).getByRole("heading", { name: "Old RSS episode" })).toBeInTheDocument();
  });
});
