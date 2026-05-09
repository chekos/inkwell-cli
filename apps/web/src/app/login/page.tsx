import { LoginForm } from "./LoginForm";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <section className="w-full max-w-md border border-border bg-surface p-6">
        <div className="mb-8">
          <span className="grid size-10 place-items-center rounded-sm bg-accent font-mono text-sm font-semibold text-accent-foreground">
            in
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight">Sign in to Inkwell</h1>
          <p className="mt-3 text-sm leading-6 text-muted">
            Save generated podcast and media notes in your private web library.
          </p>
        </div>
        <LoginForm />
      </section>
    </main>
  );
}
