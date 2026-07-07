import Link from "next/link";
import { Check, Circle, CircleAlert, Clock, Loader2 } from "lucide-react";

import type { ImportJobStage, ImportJobStatus } from "@/lib/database.types";
import { formatDate, stageLabel } from "@/lib/format";

type TimelineStep = {
  stage: ImportJobStage;
  description: string;
};

const STEPS: TimelineStep[] = [
  { stage: "queued", description: "Job is safely recorded and waiting for the worker." },
  { stage: "fetching_source", description: "Resolving the source and collecting media metadata." },
  { stage: "extracting_transcript", description: "Finding captions or transcribing the audio." },
  { stage: "generating_notes", description: "Extracting summaries, quotes, and concepts." },
  { stage: "saving_result", description: "Writing the generated markdown into your library." },
  { stage: "done", description: "The saved note is ready to read." },
];

function stepState(step: ImportJobStage, currentStage: ImportJobStage | null, status: ImportJobStatus) {
  if (status === "failed") {
    if (step === currentStage) {
      return "failed";
    }
  }

  if (status === "succeeded") {
    return "complete";
  }

  if (status === "cancelled") {
    return step === currentStage ? "cancelled" : "upcoming";
  }

  const currentIndex = STEPS.findIndex((item) => item.stage === (currentStage ?? "queued"));
  const stepIndex = STEPS.findIndex((item) => item.stage === step);

  if (stepIndex < currentIndex) {
    return "complete";
  }
  if (stepIndex === currentIndex) {
    return "current";
  }
  return "upcoming";
}

export function JobTimeline({
  status,
  stage,
  errorMessage,
  createdAt,
  startedAt,
  finishedAt,
}: {
  status: ImportJobStatus;
  stage?: ImportJobStage | null;
  errorMessage?: string | null;
  createdAt?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
}) {
  const active = status === "queued" || status === "running";

  return (
    <section className="border border-border bg-surface shadow-soft">
      <div className="border-b border-border p-5">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Import timeline</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              You can leave this page. Inkwell will keep updating the durable job record.
            </p>
          </div>
          {active ? (
            <span className="inline-flex h-8 items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 text-xs font-semibold text-accent">
              <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
              Working
            </span>
          ) : null}
        </div>
      </div>

      <ol className="divide-y divide-border">
        {STEPS.map((step) => {
          const state = stepState(step.stage, stage ?? "queued", status);
          const Icon =
            state === "complete" ? Check : state === "failed" ? CircleAlert : state === "current" ? Loader2 : Circle;

          return (
            <li key={step.stage} className="grid gap-4 p-5 sm:grid-cols-[2rem_1fr_auto] sm:items-start">
              <span
                className={`grid size-8 place-items-center rounded-full border ${
                  state === "complete"
                    ? "border-success/30 bg-success/10 text-success"
                    : state === "failed"
                      ? "border-danger/30 bg-danger/10 text-danger"
                      : state === "current"
                        ? "border-accent/30 bg-accent/10 text-accent"
                        : "border-border bg-background text-muted"
                }`}
              >
                <Icon aria-hidden="true" className={`size-4 ${state === "current" ? "animate-spin" : ""}`} />
              </span>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold">{stageLabel(step.stage)}</h3>
                  {state === "current" ? (
                    <span className="rounded-sm bg-accent/10 px-2 py-0.5 text-xs font-semibold text-accent">
                      Current
                    </span>
                  ) : null}
                  {state === "failed" ? (
                    <span className="rounded-sm bg-danger/10 px-2 py-0.5 text-xs font-semibold text-danger">
                      Needs attention
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm leading-6 text-muted">{step.description}</p>
              </div>
              <span className="hidden items-center gap-1 text-xs text-muted sm:inline-flex">
                <Clock aria-hidden="true" className="size-3" />
                {step.stage === "queued"
                  ? formatDate(createdAt)
                  : step.stage === "done"
                    ? formatDate(finishedAt)
                    : state === "upcoming"
                      ? "Pending"
                      : formatDate(startedAt)}
              </span>
            </li>
          );
        })}
      </ol>

      {status === "failed" ? (
        <div className="border-t border-danger/30 bg-danger/10 p-5">
          <h3 className="font-semibold text-danger">Import failed</h3>
          <p className="mt-2 text-sm leading-6 text-muted">
            {errorMessage ?? "The worker could not finish this import."}
          </p>
          <Link href="/app/new" className="mt-4 inline-flex h-10 items-center rounded-sm bg-accent px-3 text-sm font-semibold text-accent-foreground">
            Start another import
          </Link>
        </div>
      ) : null}
    </section>
  );
}
