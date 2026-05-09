import Link from "next/link";
import { notFound } from "next/navigation";

import { JobAutoRefresh } from "@/components/JobAutoRefresh";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate, stageLabel } from "@/lib/format";
import { getJob, getJobNote } from "@/lib/app-data";

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const job = await getJob(id);
  const note = job?.status === "succeeded" ? await getJobNote(id) : null;

  if (!job) {
    notFound();
  }

  const jobIsActive = job.status === "queued" || job.status === "running";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <JobAutoRefresh active={jobIsActive} />
      <div className="flex items-start justify-between gap-4 border-b border-border pb-6">
        <div>
          <p className="font-mono text-xs text-muted">{job.id}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Import job</h1>
        </div>
        <StatusBadge status={job.status} />
      </div>

      <section className="border border-border bg-surface p-5">
        <dl className="grid gap-5 sm:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">Stage</dt>
            <dd className="mt-1 text-sm">{stageLabel(job.stage)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">Created</dt>
            <dd className="mt-1 text-sm">{formatDate(job.created_at)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">Started</dt>
            <dd className="mt-1 text-sm">{formatDate(job.started_at)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">Finished</dt>
            <dd className="mt-1 text-sm">{formatDate(job.finished_at)}</dd>
          </div>
        </dl>
      </section>

      {job.status === "failed" ? (
        <section className="border border-danger/30 bg-danger/10 p-5">
          <h2 className="font-semibold text-danger">Import failed</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            {job.error_message ?? "The worker could not finish this import."}
          </p>
          <Link href="/app/new" className="mt-4 inline-flex text-sm font-semibold text-accent">
            Start another import
          </Link>
        </section>
      ) : null}

      {job.status === "succeeded" ? (
        <section className="border border-accent/30 bg-accent/10 p-5">
          <h2 className="font-semibold text-accent">Import complete</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            The worker finished and saved this import to your library.
          </p>
          {note ? (
            <Link
              href={`/app/notes/${note.id}`}
              className="mt-4 inline-flex h-10 items-center rounded-sm bg-accent px-3 text-sm font-semibold text-accent-foreground"
            >
              Open note
            </Link>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
