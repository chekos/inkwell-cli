# Inkwell Modal Worker

This worker receives import jobs from the Vercel app, runs the existing Python
pipeline, and writes job status plus the generated note back to Supabase.

## Local Setup

Install the worker extra:

```bash
uv sync --extra worker --dev
```

Create the Modal secret used by `workers/inkwell/modal_app.py`:

```bash
uv run modal secret create inkwell-worker \
  SUPABASE_URL="https://PROJECT.supabase.co" \
  SUPABASE_SERVICE_ROLE_KEY="..." \
  GOOGLE_API_KEY="..." \
  ANTHROPIC_API_KEY="..." \
  INKWELL_WORKER_TOKEN="..."
```

`ANTHROPIC_API_KEY` is only needed if `INKWELL_EXTRACTION_PROVIDER=claude`.
The same `INKWELL_WORKER_TOKEN` value must be configured in Vercel.

## Development

Serve the endpoint from the repo root:

```bash
uv run modal serve workers/inkwell/modal_app.py
```

Deploy the worker:

```bash
uv run modal deploy workers/inkwell/modal_app.py
```

After deployment, copy Modal's `start_import` web endpoint URL into Vercel as:

```bash
INKWELL_WORKER_ENDPOINT="https://..."
INKWELL_WORKER_DISPATCH_ENABLED="true"
INKWELL_WORKER_TOKEN="..."
```
