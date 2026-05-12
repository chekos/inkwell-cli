import { CheckCircle2, Clock3, FileText } from "lucide-react";

import { ImportCommand } from "@/components/ImportCommand";
import { PageHeader, Panel } from "@/components/ui";

const nextSteps = [
  {
    title: "Create a durable job",
    description: "The URL is saved first, so refreshes and worker retries do not lose your import.",
    icon: CheckCircle2,
  },
  {
    title: "Track worker progress",
    description: "The status page updates while Inkwell fetches, transcribes, extracts, and saves.",
    icon: Clock3,
  },
  {
    title: "Open the note",
    description: "Successful imports land in your library as readable markdown with source metadata.",
    icon: FileText,
  },
];

export default function NewImportPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <PageHeader
        title="New import"
        description="Paste one source and let the worker handle the slow parts. You can leave the status page open or come back later from the library."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Panel>
          <ImportCommand />
        </Panel>

        <Panel>
          <h2 className="text-lg font-semibold tracking-tight">What happens next</h2>
          <div className="mt-5 space-y-5">
            {nextSteps.map((step) => {
              const Icon = step.icon;

              return (
                <div key={step.title} className="flex gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full border border-accent/30 bg-accent/10 text-accent">
                    <Icon aria-hidden="true" className="size-4" />
                  </span>
                  <div>
                    <h3 className="text-sm font-semibold">{step.title}</h3>
                    <p className="mt-1 text-sm leading-6 text-muted">{step.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
    </div>
  );
}
