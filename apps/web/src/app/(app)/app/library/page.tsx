import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { getLibraryData } from "@/lib/app-data";
import { stageLabel } from "@/lib/format";

import { LibraryList } from "./LibraryList";

export default async function LibraryPage() {
  const data = await getLibraryData();

  if (!data.configured) {
    return (
      <EmptyState
        title="Library needs Supabase"
        description="Once Supabase is configured, saved notes and retryable jobs will appear here."
        actionHref="/app/settings"
        actionLabel="Open settings"
      />
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Library</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
          Recent saved notes and import jobs that still need attention.
        </p>
      </div>

      {data.notes.length === 0 ? (
        <EmptyState
          title="No saved notes"
          description="Create your first import and Inkwell will save the readable markdown here."
        />
      ) : (
        <LibraryList notes={data.notes} />
      )}

      {data.jobs.length > 0 ? (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Needs attention</h2>
          <div className="divide-y divide-border border border-border bg-surface">
            {data.jobs.map((job) => (
              <Link key={job.id} href={`/app/jobs/${job.id}`} className="flex items-center justify-between gap-4 p-4 hover:bg-surface-strong">
                <div>
                  <p className="font-mono text-xs text-muted">{job.id.slice(0, 8)}</p>
                  <p className="mt-1 text-sm text-muted">{stageLabel(job.stage)}</p>
                </div>
                <StatusBadge status={job.status} />
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
