# Inkwell Web

The Inkwell web app is a Next.js app deployed from `apps/web` on Vercel. It uses
Supabase for authentication and private library storage, then dispatches long
audio-processing jobs to the Modal worker in `workers/inkwell`.

## Development

From the repository root:

```bash
pnpm install
pnpm web:dev
```

Copy `.env.example` to `.env.local` and fill in the Supabase values to enable
sign-in, jobs, and library data.

## Environment

Required for the web app:

```bash
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Required when dispatching imports to Modal:

```bash
INKWELL_WORKER_DISPATCH_ENABLED=true
INKWELL_WORKER_ENDPOINT=
INKWELL_WORKER_TOKEN=
```

## Deployment

Create a Vercel project pointing at this GitHub repository and set the project
Root Directory to `apps/web`. The root `pnpm-workspace.yaml` keeps the web app
inside this repo without mixing Node dependencies into the Python package.
