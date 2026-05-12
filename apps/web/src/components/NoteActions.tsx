"use client";

import { Clipboard, ClipboardCheck, Download } from "lucide-react";
import { useState } from "react";

import { filenameFromTitle } from "@/lib/markdown";

export function NoteActions({ markdown, title }: { markdown: string; title: string }) {
  const [copied, setCopied] = useState(false);

  async function copyMarkdown() {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function downloadMarkdown() {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filenameFromTitle(title);
    link.click();
    URL.revokeObjectURL(url);
  }

  const CopyIcon = copied ? ClipboardCheck : Clipboard;

  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={copyMarkdown}
        className="inline-flex h-10 items-center gap-2 rounded-sm border border-border bg-surface px-3 text-sm font-semibold text-muted transition hover:border-accent hover:text-accent"
      >
        <CopyIcon aria-hidden="true" className="size-4" />
        {copied ? "Copied" : "Copy markdown"}
      </button>
      <button
        type="button"
        onClick={downloadMarkdown}
        className="inline-flex h-10 items-center gap-2 rounded-sm bg-accent px-3 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong"
      >
        <Download aria-hidden="true" className="size-4" />
        Export
      </button>
    </div>
  );
}
