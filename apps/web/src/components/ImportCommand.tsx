"use client";

import { ArrowRight, Link2, Loader2, Radio, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState, useTransition } from "react";

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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const [isPending, startTransition] = useTransition();

  const sourceKind = useMemo(() => detectSourceKind(url), [url]);
  const sourceLabel = sourceKindLabel(sourceKind);
  const isBusy = isSubmitting || isPending;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (submittingRef.current) {
      return;
    }

    setError(null);
    setNotice(null);

    let normalizedUrl: string;
    try {
      normalizedUrl = new URL(url).toString();
    } catch {
      setError("Enter a complete URL, including https://.");
      return;
    }

    submittingRef.current = true;
    setIsSubmitting(true);

    let response: Response;
    let payload: ImportPayload;

    try {
      response = await fetch("/api/imports", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ url: normalizedUrl }),
      });
      payload = (await response.json()) as ImportPayload;
    } catch {
      submittingRef.current = false;
      setIsSubmitting(false);
      setError("Could not reach Inkwell. Check your connection and try again.");
      return;
    }

    if (!response.ok || !payload.statusUrl) {
      submittingRef.current = false;
      setIsSubmitting(false);
      setError(payload.error ?? "Could not create the import job.");
      return;
    }

    setNotice(payload.dispatchReason ?? "Import job created. Opening the status page.");

    startTransition(() => {
      router.push(payload.statusUrl!);
    });
  }

  return (
    <form aria-busy={isBusy} onSubmit={submit} className={variant === "full" ? "space-y-5" : "space-y-4"}>
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
            aria-label="Source URL"
            required
            value={url}
            disabled={isBusy}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted/70 disabled:cursor-not-allowed disabled:text-muted"
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
      {isSubmitting ? (
        <p role="status" className="border border-accent/30 bg-accent/10 px-3 py-2 text-sm font-medium text-accent">
          Creating import job. The worker will open on the status page when it is ready.
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="border border-warning/30 bg-warning/10 px-3 py-2 text-sm font-medium text-warning">
          {notice}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isBusy}
        className="inline-flex h-11 items-center justify-center gap-2 rounded-sm bg-accent px-4 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isBusy ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : <ArrowRight aria-hidden="true" className="size-4" />}
        {isBusy ? "Creating import..." : "Start import"}
      </button>
    </form>
  );
}
