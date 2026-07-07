"use client";

import { useState } from "react";

import { createBrowserSupabaseClient } from "@/lib/supabase/browser";

type LoginFormProps = {
  initialError?: string | null;
};

export function LoginForm({ initialError = null }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(initialError);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setIsSubmitting(true);
    const submittedEmail = email.trim();

    try {
      const supabase = createBrowserSupabaseClient();
      const { error: signInError } = await supabase.auth.signInWithOtp({
        email: submittedEmail,
        options: { emailRedirectTo: window.location.origin },
      });

      if (signInError) {
        setError(signInError.message);
        return;
      }

      setMessage(`Email sent to ${submittedEmail}. Open the sign-in link in your inbox to continue.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in is not configured.");
    } finally {
      setIsSubmitting(false);
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
      {message ? (
        <div
          role="status"
          aria-live="polite"
          className="border border-success/30 bg-success/10 p-3 text-sm font-medium leading-6 text-success"
        >
          {message}
        </div>
      ) : null}
      {error ? (
        <div role="alert" className="border border-danger/30 bg-danger/10 p-3 text-sm font-medium leading-6 text-danger">
          {error}
        </div>
      ) : null}
      <button
        type="submit"
        disabled={isSubmitting}
        className="inline-flex h-11 w-full items-center justify-center rounded-sm bg-accent px-4 text-sm font-semibold text-accent-foreground transition disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? "Sending..." : "Send sign-in link"}
      </button>
    </form>
  );
}
