import { CheckCircle2, CircleAlert } from "lucide-react";

import { PageHeader, Panel } from "@/components/ui";
import { hasSupabasePublicEnv, isWorkerDispatchEnabled } from "@/lib/env";

const rows = [
  {
    label: "Supabase public env",
    description: "Required for auth, private libraries, and user-owned data reads.",
    key: "supabase",
  },
  {
    label: "Worker endpoint",
    description: "Required before imports can dispatch to the Modal pipeline.",
    key: "worker",
  },
  {
    label: "Worker dispatch",
    description: "When disabled, imports are durable but remain queued for local development.",
    key: "dispatch",
  },
];

export default function SettingsPage() {
  const values = {
    supabase: hasSupabasePublicEnv(),
    worker: Boolean(process.env.INKWELL_WORKER_ENDPOINT),
    dispatch: isWorkerDispatchEnabled(),
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        title="Settings"
        description="Deployment wiring for the Vercel app, Supabase project, and Modal worker."
      />

      <Panel>
        <h2 className="text-lg font-semibold tracking-tight">Environment readiness</h2>
        <dl className="mt-5 divide-y divide-border text-sm">
          {rows.map((row) => {
            const configured = values[row.key as keyof typeof values];
            const Icon = configured ? CheckCircle2 : CircleAlert;

            return (
              <div key={row.key} className="grid gap-3 py-4 sm:grid-cols-[1fr_auto] sm:items-center">
                <div>
                  <dt className="font-semibold">{row.label}</dt>
                  <dd className="mt-1 text-muted">{row.description}</dd>
                </div>
                <dd
                  className={`inline-flex h-8 w-fit items-center gap-2 rounded-full border px-3 text-xs font-semibold ${
                    configured
                      ? "border-success/30 bg-success/10 text-success"
                      : "border-warning/30 bg-warning/10 text-warning"
                  }`}
                >
                  <Icon aria-hidden="true" className="size-3.5" />
                  {configured ? "Configured" : "Missing"}
                </dd>
              </div>
            );
          })}
        </dl>
      </Panel>
    </div>
  );
}
