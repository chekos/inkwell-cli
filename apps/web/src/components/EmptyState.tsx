import Link from "next/link";
import { Plus, Sparkles } from "lucide-react";

export function EmptyState({
  title,
  description,
  actionHref = "/app/new",
  actionLabel = "New import",
}: {
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <section className="border border-dashed border-border bg-surface px-6 py-12 text-center shadow-soft">
      <span className="mx-auto grid size-11 place-items-center rounded-sm bg-accent/10 text-accent">
        <Sparkles aria-hidden="true" className="size-5" />
      </span>
      <h2 className="mt-4 text-xl font-semibold">{title}</h2>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted">{description}</p>
      <Link
        href={actionHref}
        className="mt-6 inline-flex h-11 items-center gap-2 rounded-sm bg-accent px-4 text-sm font-semibold text-accent-foreground transition hover:bg-accent/90"
      >
        <Plus aria-hidden="true" className="size-4" />
        {actionLabel}
      </Link>
    </section>
  );
}
