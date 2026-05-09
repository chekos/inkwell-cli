import { hasSupabasePublicEnv, isWorkerDispatchEnabled } from "@/lib/env";

export default function SettingsPage() {
  const supabaseConfigured = hasSupabasePublicEnv();
  const workerConfigured = Boolean(process.env.INKWELL_WORKER_ENDPOINT);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Deployment wiring for the Vercel app, Supabase project, and Modal worker.
        </p>
      </div>

      <section className="border border-border bg-surface p-5">
        <h2 className="font-semibold">Environment</h2>
        <dl className="mt-5 divide-y divide-border text-sm">
          <div className="flex items-center justify-between py-3">
            <dt className="text-muted">Supabase public env</dt>
            <dd className="font-medium">{supabaseConfigured ? "Configured" : "Missing"}</dd>
          </div>
          <div className="flex items-center justify-between py-3">
            <dt className="text-muted">Worker endpoint</dt>
            <dd className="font-medium">{workerConfigured ? "Configured" : "Missing"}</dd>
          </div>
          <div className="flex items-center justify-between py-3">
            <dt className="text-muted">Worker dispatch</dt>
            <dd className="font-medium">{isWorkerDispatchEnabled() ? "Enabled" : "Disabled"}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
