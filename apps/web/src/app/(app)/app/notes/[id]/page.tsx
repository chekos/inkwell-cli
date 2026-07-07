import { ExternalLink } from "lucide-react";
import { notFound } from "next/navigation";

import { MarkdownViewer } from "@/components/MarkdownViewer";
import { NoteActions } from "@/components/NoteActions";
import { NoteOutline } from "@/components/NoteOutline";
import { PageHeader } from "@/components/ui";
import { getNote } from "@/lib/app-data";
import { formatDate } from "@/lib/format";
import { extractMarkdownHeadings } from "@/lib/markdown";
import { detectSourceKind, sourceHost, sourceKindLabel } from "@/lib/source";

export default async function NotePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const note = await getNote(id);

  if (!note) {
    notFound();
  }

  const headings = extractMarkdownHeadings(note.body_markdown);
  const sourceKind = sourceKindLabel(note.source?.source_type ?? detectSourceKind(note.source?.url));

  return (
    <div className="space-y-8">
      <PageHeader
        title={note.title}
        description={note.summary ?? undefined}
        meta={
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-muted">
            <span>{formatDate(note.created_at)}</span>
            <span aria-hidden="true">/</span>
            <span>{sourceKind}</span>
            {note.source?.url ? (
              <>
                <span aria-hidden="true">/</span>
                <a
                  href={note.source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-accent hover:underline"
                >
                  {sourceHost(note.source.url)}
                  <ExternalLink aria-hidden="true" className="size-3" />
                </a>
              </>
            ) : null}
          </div>
        }
        action={<NoteActions markdown={note.body_markdown} title={note.title} />}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,48rem)_16rem]">
        <section className="border border-border bg-surface p-5 shadow-soft sm:p-7">
          <MarkdownViewer markdown={note.body_markdown} />
        </section>
        <NoteOutline headings={headings} />
      </div>
    </div>
  );
}
