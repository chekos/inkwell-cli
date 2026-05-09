import { notFound } from "next/navigation";

import { CopyMarkdownButton } from "@/components/CopyMarkdownButton";
import { MarkdownViewer } from "@/components/MarkdownViewer";
import { getNote } from "@/lib/app-data";
import { formatDate } from "@/lib/format";

export default async function NotePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const note = await getNote(id);

  if (!note) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-3xl">
      <header className="flex flex-col justify-between gap-5 border-b border-border pb-6 sm:flex-row sm:items-start">
        <div>
          <p className="font-mono text-xs text-muted">{formatDate(note.created_at)}</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight">{note.title}</h1>
          {note.summary ? (
            <p className="mt-4 text-sm leading-6 text-muted">{note.summary}</p>
          ) : null}
        </div>
        <CopyMarkdownButton markdown={note.body_markdown} />
      </header>

      <section className="mt-8 border border-border bg-surface p-6">
        <MarkdownViewer markdown={note.body_markdown} />
      </section>
    </div>
  );
}
