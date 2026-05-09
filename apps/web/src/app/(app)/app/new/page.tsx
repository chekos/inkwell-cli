import { ImportForm } from "./ImportForm";

export default function NewImportPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-3xl font-semibold tracking-tight">New import</h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        Create a durable job first. The worker can run separately, and you can leave this page
        without losing progress.
      </p>
      <section className="mt-8 border border-border bg-surface p-5">
        <ImportForm />
      </section>
    </div>
  );
}
