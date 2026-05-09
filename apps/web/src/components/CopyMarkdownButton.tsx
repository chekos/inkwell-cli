"use client";

import { Clipboard, ClipboardCheck } from "lucide-react";
import { useState } from "react";

export function CopyMarkdownButton({ markdown }: { markdown: string }) {
  const [copied, setCopied] = useState(false);

  async function copyMarkdown() {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  const Icon = copied ? ClipboardCheck : Clipboard;

  return (
    <button
      type="button"
      onClick={copyMarkdown}
      className="inline-flex h-10 shrink-0 items-center gap-2 rounded-sm border border-border px-3 text-sm font-medium text-muted transition hover:border-accent hover:text-accent"
    >
      <Icon className="size-4" aria-hidden="true" />
      {copied ? "Copied" : "Copy markdown"}
    </button>
  );
}
