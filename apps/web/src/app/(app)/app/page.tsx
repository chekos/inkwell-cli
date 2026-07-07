import Link from "next/link";
import { ArrowRight, Clock3, FileText } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { ImportCommand } from "@/components/ImportCommand";
import { StatusBadge } from "@/components/StatusBadge";
import { MetricCard, PageHeader, Panel, SectionTitle } from "@/components/ui";
import { formatDate, stageLabel } from "@/lib/format";
import { getDashboardData } from "@/lib/app-data";
import { detectSourceKind, sourceHost, sourceKindLabel } from "@/lib/source";

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

  const activeJobs = data.jobs.filter((job) => job.status === "queued" || job.status === "running").length;
  const failedJobs = data.jobs.filter((job) => job.status === "failed").length;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Your Inkwell library"
        description="Paste a media or feed URL, watch the Python pipeline work, and keep the generated markdown in one private place."
        action={
          <Link
            href="/app/new"
            className="inline-flex h-11 items-center justify-center gap-2 rounded-sm bg-accent px-4 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong"
          >
            New import
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Panel>
          <ImportCommand variant="compact" />
        </Panel>
        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
          <MetricCard label="Saved notes" value={data.notes.length} tone="success" />
          <MetricCard label="Active jobs" value={activeJobs} tone="accent" />
          <MetricCard label="Needs attention" value={failedJobs} tone={failedJobs > 0 ? "danger" : "neutral"} />
        </div>
      </div>

      {data.notes.length === 0 && data.jobs.length === 0 ? (
        <EmptyState
          title="No notes yet"
          description="Start with a podcast episode, YouTube URL, or supported feed. Inkwell will save the generated output here when the worker finishes."
        />
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr]">
          <section>
            <SectionTitle title="Recent notes" actionHref="/app/library" actionLabel="View library" />
            <div className="divide-y divide-border border border-border bg-surface shadow-soft">
              {data.notes.map((note) => (
                <Link
                  key={note.id}
                  href={`/app/notes/${note.id}`}
                  className="grid gap-3 p-4 transition hover:bg-surface-strong sm:grid-cols-[2rem_1fr_auto]"
                >
                  <span className="grid size-8 place-items-center rounded-sm bg-accent/10 text-accent">
                    <FileText aria-hidden="true" className="size-4" />
                  </span>
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold">{note.title}</h3>
                      <span className="rounded-sm border border-border bg-background px-2 py-0.5 text-xs font-semibold text-muted">
                        {sourceKindLabel(note.source?.source_type ?? detectSourceKind(note.source?.url))}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">
                      {note.summary ?? "Saved markdown note"}
                    </p>
                  </div>
                  <p className="text-sm text-muted sm:text-right">{formatDate(note.created_at)}</p>
                </Link>
              ))}
            </div>
          </section>

          <section>
            <SectionTitle title="Recent jobs" description="Worker progress and recoverable failures." />
            <div className="divide-y divide-border border border-border bg-surface shadow-soft">
              {data.jobs.map((job) => (
                <Link key={job.id} href={`/app/jobs/${job.id}`} className="block p-4 transition hover:bg-surface-strong">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold">{sourceHost(job.source?.url)}</span>
                    <StatusBadge status={job.status} />
                  </div>
                  <p className="mt-2 flex items-center gap-2 text-sm text-muted">
                    <Clock3 aria-hidden="true" className="size-3.5" />
                    {stageLabel(job.stage)}
                  </p>
                </Link>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
