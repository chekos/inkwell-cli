"use client";

import { ArrowDownAZ, Clock3, FileText, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import type { LibraryNote } from "@/lib/app-data";
import { formatDate } from "@/lib/format";
import { detectSourceKind, sourceHost, sourceKindLabel } from "@/lib/source";

type Filter = "all" | "summaries" | "recent";
type Sort = "newest" | "updated" | "title";

export function LibraryList({ notes }: { notes: LibraryNote[] }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("newest");

  const filteredNotes = useMemo(() => {
    const needle = query.trim().toLowerCase();

    const results = notes
      .filter((note) => {
        if (filter === "summaries" && !note.summary) {
          return false;
        }

        if (!needle) {
          return true;
        }

        return [note.title, note.summary ?? "", note.source?.url ?? "", note.source?.title ?? ""].some((value) =>
          value.toLowerCase().includes(needle),
        );
      })
      .sort((a, b) => {
        if (sort === "title") {
          return a.title.localeCompare(b.title);
        }

        const aDate = sort === "updated" ? a.updated_at : a.created_at;
        const bDate = sort === "updated" ? b.updated_at : b.created_at;
        return new Date(bDate).getTime() - new Date(aDate).getTime();
      });

    return filter === "recent" ? results.slice(0, 5) : results;
  }, [filter, notes, query, sort]);

  return (
    <section className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto]">
        <label className="relative block">
          <span className="sr-only">Search library</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search notes, summaries, or sources"
            className="h-11 w-full border border-border bg-surface pl-10 pr-3 text-sm outline-none transition focus:border-accent"
          />
        </label>

        <div className="flex rounded-sm border border-border bg-surface p-1" aria-label="Filter notes">
          {[
            ["all", "All"],
            ["summaries", "Summaries"],
            ["recent", "Recent"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value as Filter)}
              className={`h-9 px-3 text-sm font-semibold transition ${
                filter === value ? "bg-accent text-accent-foreground" : "text-muted hover:bg-surface-strong"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <label className="flex h-11 items-center gap-2 border border-border bg-surface px-3 text-sm text-muted">
          <ArrowDownAZ aria-hidden="true" className="size-4" />
          <span className="sr-only">Sort notes</span>
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as Sort)}
            className="bg-transparent font-semibold text-foreground outline-none"
          >
            <option value="newest">Newest</option>
            <option value="updated">Updated</option>
            <option value="title">Title</option>
          </select>
        </label>
      </div>

      {filteredNotes.length === 0 ? (
        <div className="border border-border bg-surface p-5 text-sm text-muted shadow-soft">
          No notes match that search.
        </div>
      ) : (
        <div className="divide-y divide-border border border-border bg-surface shadow-soft">
          {filteredNotes.map((note) => {
            const sourceKind = sourceKindLabel(note.source?.source_type ?? detectSourceKind(note.source?.url));

            return (
              <Link
                key={note.id}
                href={`/app/notes/${note.id}`}
                className="grid gap-3 p-4 transition hover:bg-surface-strong md:grid-cols-[2rem_minmax(0,1fr)_10rem]"
              >
                <span className="grid size-8 place-items-center rounded-sm bg-accent/10 text-accent">
                  <FileText aria-hidden="true" className="size-4" />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold">{note.title}</h2>
                    <span className="rounded-sm border border-border bg-background px-2 py-0.5 text-xs font-semibold text-muted">
                      {sourceKind}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">
                    {note.summary ?? "Saved markdown note"}
                  </p>
                  <p className="mt-2 text-xs text-muted">{sourceHost(note.source?.url)}</p>
                </div>
                <p className="flex items-center gap-1 text-sm text-muted md:justify-end md:text-right">
                  <Clock3 aria-hidden="true" className="size-3.5" />
                  {formatDate(note.created_at)}
                </p>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
