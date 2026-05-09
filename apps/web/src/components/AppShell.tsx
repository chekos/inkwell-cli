import Link from "next/link";
import { BookOpen, Plus, Settings } from "lucide-react";

const navItems = [
  { href: "/app/new", label: "New", icon: Plus },
  { href: "/app/library", label: "Library", icon: BookOpen },
  { href: "/app/settings", label: "Settings", icon: Settings },
];

export function AppShell({
  children,
  email,
}: {
  children: React.ReactNode;
  email?: string | null;
}) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-surface/90">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/app" className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-sm bg-accent font-mono text-sm font-semibold text-accent-foreground">
              in
            </span>
            <span>
              <span className="block text-base font-semibold leading-5">Inkwell</span>
              <span className="block text-xs text-muted">Private notes from media</span>
            </span>
          </Link>

          <nav className="hidden items-center gap-1 sm:flex">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="inline-flex h-10 items-center gap-2 rounded-sm px-3 text-sm font-medium text-muted transition hover:bg-surface-strong hover:text-foreground"
                >
                  <Icon aria-hidden="true" className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="hidden max-w-52 truncate text-right text-xs text-muted md:block">
            {email ?? "Local setup"}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>

      <nav className="fixed inset-x-0 bottom-0 border-t border-border bg-surface/95 px-3 py-2 sm:hidden">
        <div className="grid grid-cols-3 gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex h-12 flex-col items-center justify-center gap-1 rounded-sm text-xs font-medium text-muted"
              >
                <Icon aria-hidden="true" className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
