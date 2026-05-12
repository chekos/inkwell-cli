"use client";

import Link from "next/link";
import { BookOpen, Home, Plus, Settings } from "lucide-react";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/app", label: "Home", icon: Home },
  { href: "/app/new", label: "New import", icon: Plus },
  { href: "/app/library", label: "Library", icon: BookOpen },
  { href: "/app/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string) {
  if (href === "/app") {
    return pathname === "/app";
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNav({ mode = "desktop" }: { mode?: "desktop" | "mobile" }) {
  const pathname = usePathname();

  if (mode === "mobile") {
    return (
      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface/95 px-3 py-2 backdrop-blur sm:hidden">
        <div className="grid grid-cols-4 gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex h-12 flex-col items-center justify-center gap-1 rounded-sm text-[0.7rem] font-semibold transition ${
                  active ? "bg-accent text-accent-foreground" : "text-muted hover:bg-surface-strong hover:text-foreground"
                }`}
              >
                <Icon aria-hidden="true" className="size-4" />
                <span className="max-w-full truncate">{item.label.replace(" import", "")}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    );
  }

  return (
    <nav className="space-y-1" aria-label="Primary navigation">
      {navItems.map((item) => {
        const Icon = item.icon;
        const active = isActive(pathname, item.href);

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`flex h-10 items-center gap-3 rounded-sm px-3 text-sm font-semibold transition ${
              active
                ? "bg-accent text-accent-foreground shadow-soft"
                : "text-muted hover:bg-surface-strong hover:text-foreground"
            }`}
          >
            <Icon aria-hidden="true" className="size-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
