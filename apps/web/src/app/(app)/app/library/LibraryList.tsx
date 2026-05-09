"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import type { LibraryNote } from "@/lib/app-data";
import { formatDate } from "@/lib/format";

export function LibraryList({ notes }: { notes: LibraryNote[] }) {
  const [query, setQuery] = useState("");
  const filteredNotes = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return notes;
    }

    return notes.filter((note) =>
      [note.title, note.summary ?? ""].some((value) => value.toLowerCase().includes(needle)),
    );
  }, [notes, query]);

  return (
    <section className="space-y-4">
      <label className="relative block">
        <span className="sr-only">Search library</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search notes"
          className="h-11 w-full border border-border bg-surface pl-10 pr-3 text-sm outline-none transition focus:border-accent"
        />
      </label>

      {filteredNotes.length === 0 ? (
        <div className="border border-border bg-surface p-5 text-sm text-muted">
          No notes match that search.
        </div>
      ) : (
        <div className="divide-y divide-border border border-border bg-surface">
          {filteredNotes.map((note) => (
            <Link
              key={note.id}
              href={`/app/notes/${note.id}`}
              className="grid gap-3 p-4 hover:bg-surface-strong md:grid-cols-[1fr_10rem]"
            >
              <div>
                <h2 className="font-semibold">{note.title}</h2>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">
                  {note.summary ?? "Saved markdown note"}
                </p>
              </div>
              <p className="text-sm text-muted md:text-right">{formatDate(note.created_at)}</p>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
