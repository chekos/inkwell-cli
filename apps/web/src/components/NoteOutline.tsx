import Link from "next/link";

import type { MarkdownHeading } from "@/lib/markdown";

export function NoteOutline({ headings }: { headings: MarkdownHeading[] }) {
  if (headings.length === 0) {
    return null;
  }

  return (
    <aside className="hidden xl:block">
      <div className="sticky top-8 border border-border bg-surface p-4 shadow-soft">
        <h2 className="text-xs font-semibold uppercase text-muted">Sections</h2>
        <nav className="mt-3 space-y-1" aria-label="Note sections">
          {headings.slice(0, 12).map((heading) => (
            <Link
              key={`${heading.level}-${heading.id}-${heading.text}`}
              href={`#${heading.id}`}
              className={`block rounded-sm px-2 py-1.5 text-sm leading-5 transition hover:bg-surface-strong hover:text-foreground ${
                heading.level === 1 ? "font-semibold text-foreground" : "text-muted"
              } ${heading.level === 3 ? "pl-5 text-xs" : ""}`}
            >
              {heading.text}
            </Link>
          ))}
        </nav>
      </div>
    </aside>
  );
}
