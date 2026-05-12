import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { notFound } from "next/navigation";

import { JobAutoRefresh } from "@/components/JobAutoRefresh";
import { JobTimeline } from "@/components/JobTimeline";
import { StatusBadge } from "@/components/StatusBadge";
import { PageHeader, Panel } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { getJob, getJobNote } from "@/lib/app-data";
import { detectSourceKind, sourceHost, sourceKindLabel } from "@/lib/source";

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const job = await getJob(id);
  const note = job?.status === "succeeded" ? await getJobNote(id) : null;

  if (!job) {
    notFound();
  }

  const jobIsActive = job.status === "queued" || job.status === "running";
  const sourceKind = sourceKindLabel(job.source?.source_type ?? detectSourceKind(job.source?.url));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <JobAutoRefresh active={jobIsActive} />

      <PageHeader
        title={job.source?.title ?? "Import job"}
        description={`${sourceKind} from ${sourceHost(job.source?.url)}.`}
        meta={
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-muted">{job.id}</span>
            <StatusBadge status={job.status} />
          </div>
        }
        action={
          note ? (
            <Link
              href={`/app/notes/${note.id}`}
              className="inline-flex h-10 items-center gap-2 rounded-sm bg-accent px-3 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong"
            >
              Open note
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          ) : null
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <JobTimeline
          status={job.status}
          stage={job.stage}
          errorMessage={job.error_message}
          createdAt={job.created_at}
          startedAt={job.started_at}
          finishedAt={job.finished_at}
        />

        <Panel>
          <h2 className="text-lg font-semibold tracking-tight">Job details</h2>
          <dl className="mt-5 space-y-4 text-sm">
            <div>
              <dt className="text-xs font-semibold uppercase text-muted">Created</dt>
              <dd className="mt-1">{formatDate(job.created_at)}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase text-muted">Started</dt>
              <dd className="mt-1">{formatDate(job.started_at)}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase text-muted">Finished</dt>
              <dd className="mt-1">{formatDate(job.finished_at)}</dd>
            </div>
            {job.source?.url ? (
              <div>
                <dt className="text-xs font-semibold uppercase text-muted">Source</dt>
                <dd className="mt-1">
                  <a
                    href={job.source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 break-all font-medium text-accent hover:underline"
                  >
                    {sourceHost(job.source.url)}
                    <ExternalLink aria-hidden="true" className="size-3" />
                  </a>
                </dd>
              </div>
            ) : null}
          </dl>
        </Panel>
      </div>
    </div>
  );
}
