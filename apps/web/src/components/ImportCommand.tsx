"use client";

import { ArrowRight, Link2, Loader2, Radio, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

import { detectSourceKind, sourceKindLabel } from "@/lib/source";

type ImportPayload = {
  statusUrl?: string;
  error?: string;
  dispatchReason?: string;
};

export function ImportCommand({
  title = "Paste any supported media URL",
  description = "Start with a podcast episode, YouTube URL, RSS feed, or direct media file. Inkwell creates a durable worker job and saves the generated markdown when it finishes.",
  variant = "full",
}: {
  title?: string;
  description?: string;
  variant?: "full" | "compact";
}) {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const sourceKind = useMemo(() => detectSourceKind(url), [url]);
  const sourceLabel = sourceKindLabel(sourceKind);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    let normalizedUrl: string;
    try {
      normalizedUrl = new URL(url).toString();
    } catch {
      setError("Enter a complete URL, including https://.");
      return;
    }

    const response = await fetch("/api/imports", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ url: normalizedUrl }),
    });

    const payload = (await response.json()) as ImportPayload;

    if (!response.ok || !payload.statusUrl) {
      setError(payload.error ?? "Could not create the import job.");
      return;
    }

    if (payload.dispatchReason) {
      setNotice(payload.dispatchReason);
    }

    startTransition(() => {
      router.push(payload.statusUrl!);
    });
  }

  return (
    <form onSubmit={submit} className={variant === "full" ? "space-y-5" : "space-y-4"}>
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-sm bg-accent/10 text-accent">
          <Sparkles aria-hidden="true" className="size-5" />
        </span>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
        </div>
      </div>

      <label className="block" htmlFor="source-url">
        <span className="mb-2 block text-sm font-semibold">Source URL</span>
        <span className="flex min-h-14 items-center gap-3 border border-border bg-background px-4 transition focus-within:border-accent focus-within:bg-surface">
          <Link2 aria-hidden="true" className="size-4 shrink-0 text-muted" />
          <input
            id="source-url"
            type="url"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted/70"
          />
          {sourceKind !== "unknown" ? (
            <span className="hidden shrink-0 rounded-sm border border-border bg-surface px-2 py-1 text-xs font-semibold text-muted sm:inline-flex">
              {sourceLabel}
            </span>
          ) : null}
        </span>
      </label>

      {variant === "full" ? (
        <div className="grid gap-2 text-sm text-muted sm:grid-cols-3">
          {["YouTube videos", "Podcast episodes", "RSS feeds"].map((item) => (
            <div key={item} className="flex items-center gap-2 border border-border bg-background px-3 py-2">
              <Radio aria-hidden="true" className="size-3.5 text-accent" />
              {item}
            </div>
          ))}
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="border border-danger/30 bg-danger/10 px-3 py-2 text-sm font-medium text-danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="border border-warning/30 bg-warning/10 px-3 py-2 text-sm font-medium text-warning">
          {notice}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isPending}
        className="inline-flex h-11 items-center justify-center gap-2 rounded-sm bg-accent px-4 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : <ArrowRight aria-hidden="true" className="size-4" />}
        {isPending ? "Creating job..." : "Start import"}
      </button>
    </form>
  );
}
