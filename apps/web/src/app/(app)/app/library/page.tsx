import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { PageHeader, SectionTitle } from "@/components/ui";
import { getLibraryData } from "@/lib/app-data";
import { stageLabel } from "@/lib/format";
import { sourceHost } from "@/lib/source";

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
      <PageHeader
        title="Library"
        description="Search saved notes, scan source context, and return to import jobs that still need attention."
      />

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
          <SectionTitle title="Needs attention" description="Queued, running, failed, or cancelled jobs remain visible here." />
          <div className="divide-y divide-border border border-border bg-surface shadow-soft">
            {data.jobs.map((job) => (
              <Link
                key={job.id}
                href={`/app/jobs/${job.id}`}
                className="flex items-center justify-between gap-4 p-4 transition hover:bg-surface-strong"
              >
                <div>
                  <p className="font-semibold">{sourceHost(job.source?.url)}</p>
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
