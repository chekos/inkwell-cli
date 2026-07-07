# Inkwell Modal Worker

This worker receives import jobs from the Vercel app, runs the existing Python
pipeline, and writes job status plus the generated note back to Supabase.

## Runtime Behavior

The production worker exposes one authenticated `start_import` web endpoint.
That endpoint validates the request token, spawns the long-running
`process_import` Modal function, and returns the Modal function-call id to the
web app. `process_import` then updates the Supabase `import_jobs` row, runs the
Python pipeline, and upserts the final note.

For YouTube imports the transcription path is:

1. Try free YouTube captions/transcripts.
2. If YouTube blocks captions or the video has no usable caption language, try
   Gemini's public YouTube URL input in bounded clips.
3. If URL input is unavailable, fall back to downloading audio and transcribing
   the audio file with Gemini.

The worker also resolves public YouTube titles through oEmbed before invoking
the pipeline so saved notes use human-readable titles when possible.

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

## Production Verification

After deploying the worker and web app:

1. Sign in to the Vercel app.
2. Start an import from `/app/new`.
3. Open the job page and confirm it moves from `queued` to `running` to `done`.
4. Open the saved note and confirm the title, summary, and markdown body render.
5. If a job stalls or fails, inspect the Modal function-call logs:

```bash
uv run modal app logs inkwell-worker --function-call <function-call-id> --timestamps --show-function-call-id
```

For YouTube failures from cloud-IP blocking, the logs should show the worker
trying captions first, then `Transcribing YouTube URL clip ... with Gemini`.
