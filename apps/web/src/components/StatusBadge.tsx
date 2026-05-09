import type { ImportJobStatus } from "@/lib/database.types";

const LABELS: Record<ImportJobStatus, string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Done",
  failed: "Failed",
  cancelled: "Cancelled",
};

const STYLES: Record<ImportJobStatus, string> = {
  queued: "border-border bg-surface text-muted",
  running: "border-accent/30 bg-accent/10 text-accent",
  succeeded: "border-success/30 bg-success/10 text-success",
  failed: "border-danger/30 bg-danger/10 text-danger",
  cancelled: "border-border bg-surface-strong text-muted",
};

export function StatusBadge({ status }: { status: ImportJobStatus }) {
  return (
    <span
      className={`inline-flex h-7 items-center rounded-full border px-2.5 text-xs font-medium ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
