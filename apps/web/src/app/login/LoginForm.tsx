"use client";

import { useState } from "react";

import { createBrowserSupabaseClient } from "@/lib/supabase/browser";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      const supabase = createBrowserSupabaseClient();
      const { error: signInError } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=/app` },
      });

      if (signInError) {
        setError(signInError.message);
        return;
      }

      setMessage("Check your email for a sign-in link.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in is not configured.");
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <label htmlFor="email" className="block text-sm font-semibold">
        Email
      </label>
      <input
        id="email"
        type="email"
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="you@example.com"
        className="h-12 w-full border border-border bg-background px-3 text-sm outline-none transition focus:border-accent"
      />
      {message ? <p className="text-sm font-medium text-success">{message}</p> : null}
      {error ? <p className="text-sm font-medium text-danger">{error}</p> : null}
      <button
        type="submit"
        className="inline-flex h-11 w-full items-center justify-center rounded-sm bg-accent px-4 text-sm font-semibold text-accent-foreground"
      >
        Send sign-in link
      </button>
    </form>
  );
}
