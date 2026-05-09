"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

export function ImportForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const response = await fetch("/api/imports", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const payload = (await response.json()) as { statusUrl?: string; error?: string };

    if (!response.ok || !payload.statusUrl) {
      setError(payload.error ?? "Could not create the import job.");
      return;
    }

    startTransition(() => {
      router.push(payload.statusUrl!);
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <label htmlFor="url" className="block text-sm font-semibold">
        Source URL
      </label>
      <input
        id="url"
        type="url"
        required
        value={url}
        onChange={(event) => setUrl(event.target.value)}
        placeholder="https://www.youtube.com/watch?v=..."
        className="h-14 w-full border border-border bg-surface px-4 text-base outline-none transition focus:border-accent"
      />
      <p className="text-sm leading-6 text-muted">
        Paste a podcast episode, YouTube URL, or supported RSS feed. Provider choices stay out of
        the way for the MVP.
      </p>
      {error ? <p className="text-sm font-medium text-danger">{error}</p> : null}
      <button
        type="submit"
        disabled={isPending}
        className="inline-flex h-11 items-center rounded-sm bg-accent px-4 text-sm font-semibold text-accent-foreground disabled:opacity-60"
      >
        {isPending ? "Creating job..." : "Start import"}
      </button>
    </form>
  );
}
