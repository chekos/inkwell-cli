import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate, stageLabel } from "@/lib/format";
import { getDashboardData } from "@/lib/app-data";

export default async function DashboardPage() {
  const data = await getDashboardData();

  if (!data.configured) {
    return (
      <EmptyState
        title="Connect Supabase to start saving notes"
        description="The web app shell is ready. Add Supabase environment variables to enable sign-in, private libraries, and durable import jobs."
        actionHref="/app/settings"
        actionLabel="Open settings"
      />
    );
  }

  return (
    <div className="space-y-8">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-8 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Your Inkwell library</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
            Paste a media or feed URL, let the Python pipeline work, and keep the generated
            markdown in one private place.
          </p>
        </div>
        <Link
          href="/app/new"
          className="inline-flex h-11 items-center justify-center rounded-sm bg-accent px-4 text-sm font-semibold text-accent-foreground"
        >
          New import
        </Link>
      </section>

      {data.notes.length === 0 && data.jobs.length === 0 ? (
        <EmptyState
          title="No notes yet"
          description="Start with a podcast episode, YouTube URL, or supported feed. Inkwell will save the generated output here when the worker finishes."
        />
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr]">
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Recent notes</h2>
              <Link href="/app/library" className="text-sm font-medium text-accent">
                View library
              </Link>
            </div>
            <div className="divide-y divide-border border border-border bg-surface">
              {data.notes.map((note) => (
                <Link key={note.id} href={`/app/notes/${note.id}`} className="block p-4 hover:bg-surface-strong">
                  <h3 className="font-medium">{note.title}</h3>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">
                    {note.summary ?? "Saved markdown note"}
                  </p>
                  <p className="mt-3 text-xs text-muted">{formatDate(note.created_at)}</p>
                </Link>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Recent jobs</h2>
            <div className="divide-y divide-border border border-border bg-surface">
              {data.jobs.map((job) => (
                <Link key={job.id} href={`/app/jobs/${job.id}`} className="block p-4 hover:bg-surface-strong">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs text-muted">{job.id.slice(0, 8)}</span>
                    <StatusBadge status={job.status} />
                  </div>
                  <p className="mt-3 text-sm text-muted">{stageLabel(job.stage)}</p>
                </Link>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
