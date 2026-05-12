import { LoginForm } from "./LoginForm";

type LoginPageProps = {
  searchParams?: Promise<{
    error?: string | string[];
  }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = searchParams ? await searchParams : {};
  const error = Array.isArray(params.error) ? params.error[0] : params.error;

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <section className="w-full max-w-md border border-border bg-surface p-6 shadow-soft">
        <div className="mb-8">
          <span className="grid size-10 place-items-center rounded-sm bg-accent font-mono text-sm font-semibold text-accent-foreground">
            in
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight">Sign in to Inkwell</h1>
          <p className="mt-3 text-sm leading-6 text-muted">
            Save generated podcast and media notes in your private web library. We will send a secure magic link to continue.
          </p>
        </div>
        <LoginForm initialError={getLoginErrorMessage(error)} />
      </section>
    </main>
  );
}

function getLoginErrorMessage(error: string | undefined) {
  switch (error) {
    case "callback_error":
      return "That sign-in link could not be completed. Please request a fresh link.";
    case "auth_callback_failed":
      return "That sign-in link expired or was opened somewhere that did not start the request. Please request a fresh link.";
    case "auth_confirm_failed":
      return "That sign-in link is invalid or expired. Please request a fresh link.";
    default:
      return null;
  }
}
