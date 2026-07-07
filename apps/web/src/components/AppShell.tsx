import Link from "next/link";
import { Sparkles } from "lucide-react";

import { AppNav } from "@/components/AppNav";

export function AppShell({
  children,
  email,
}: {
  children: React.ReactNode;
  email?: string | null;
}) {
  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-[17rem] border-r border-border bg-surface/90 px-4 py-5 backdrop-blur lg:block">
        <div className="flex h-full flex-col">
          <Link href="/app" className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-sm bg-accent font-mono text-sm font-semibold text-accent-foreground">
              in
            </span>
            <span>
              <span className="block text-base font-semibold leading-5">Inkwell</span>
              <span className="block text-xs text-muted">Private notes from media</span>
            </span>
          </Link>

          <div className="mt-8">
            <AppNav />
          </div>

          <div className="mt-auto border border-border bg-background p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-accent">
              <Sparkles aria-hidden="true" className="size-3.5" />
              Import pipeline
            </div>
            <p className="mt-2 text-xs leading-5 text-muted">
              Paste media, watch the worker, keep the generated markdown.
            </p>
            <p className="mt-4 truncate text-xs text-muted">{email ?? "Local setup"}</p>
          </div>
        </div>
      </aside>

      <header className="border-b border-border bg-surface/90 lg:hidden">
        <div className="flex items-center justify-between px-4 py-4">
          <Link href="/app" className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-sm bg-accent font-mono text-sm font-semibold text-accent-foreground">
              in
            </span>
            <span>
              <span className="block text-base font-semibold leading-5">Inkwell</span>
              <span className="block text-xs text-muted">Private notes from media</span>
            </span>
          </Link>
          <span className="max-w-36 truncate text-right text-xs text-muted">{email ?? "Local setup"}</span>
        </div>
      </header>

      <main className="px-4 py-7 pb-24 sm:px-6 lg:ml-[17rem] lg:px-8 lg:py-8">
        <div className="mx-auto max-w-7xl">{children}</div>
      </main>

      <AppNav mode="mobile" />
    </div>
  );
}
