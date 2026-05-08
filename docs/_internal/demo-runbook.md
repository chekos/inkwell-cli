# Inkwell demo runbook (OBRA-74)

Operations reference for the public try-it demo. Companions: the
[OBRA-73 plan](../../docs/building-in-public/devlog/) for design
context, the m5 PR for deploy mechanics.

## Service outline

- **Service name**: `inkwell-demo` (Cloud Run).
- **Image**: built from this repo's top-level `Dockerfile`. Pushed to
  Artifact Registry per `.github/workflows/demo-deploy.yml`.
- **Process**: `uvicorn inkwell.demo.app:create_app --factory`,
  concurrency = 1 per Cloud Run instance, `max-instances=3` until we
  have real cost data.
- **Health probe**: `GET /healthz` returns `{"status":"ok"}`.

## Required environment variables

Set on the Cloud Run service via Secret Manager mounts (production)
or `.env` (local):

| Variable | Purpose |
| --- | --- |
| `GOOGLE_API_KEY` | Gemini API key for transcription + extraction. |
| `INKWELL_DEMO_HASH_SALT` | Per-deploy salt for SHA-256 hashing of email/URL/IP. **Rotating this is the abuse-incident response.** |
| `DEMO_PIPELINE_ENABLED` | Kill switch. `false` pauses processing; emails still record. |
| `INKWELL_DEMO_TRUSTED_PROXY_COUNT` | Trusted proxy hops in front of Cloud Run. Default `1` for the standard GCLB chain. |
| `INKWELL_DEMO_MONTHLY_SPEND_CAP_USD` | Override the default `$50` monthly cap (rarely needed). |

Anthropic key (`ANTHROPIC_API_KEY`) is *not* required for the demo —
extraction is pinned to Gemini Flash.

## Operator actions

### Pause processing without a redeploy

```bash
gcloud run services update inkwell-demo \
    --project=$GCP_PROJECT_ID --region=$GCP_REGION \
    --update-env-vars=DEMO_PIPELINE_ENABLED=false
```

The service still accepts emails (`/jobs` returns 503 maintenance with
the email recorded for acquisition signal) but refuses to enqueue
pipeline runs. Reverse with `=true`.

### Rotate the hash salt (abuse incident response)

The SHA-256 hashes of email, URL, and IP all derive from
`INKWELL_DEMO_HASH_SALT`. Rotating the salt invalidates every
rate-limit counter (no operator can tie pre-rotation hashes to
post-rotation), without touching code:

```bash
new_salt=$(openssl rand -hex 32)
gcloud secrets versions add inkwell-demo-hash-salt \
    --project=$GCP_PROJECT_ID --data-file=<(printf '%s' "$new_salt")
gcloud run services update inkwell-demo \
    --project=$GCP_PROJECT_ID --region=$GCP_REGION \
    --set-secrets=INKWELL_DEMO_HASH_SALT=inkwell-demo-hash-salt:latest
```

Existing in-flight jobs keep their old hash and run to completion;
new submissions hash with the new salt.

### Check monthly spend

The spend cap pauses the service automatically when the per-month
cumulative cost reaches `INKWELL_DEMO_MONTHLY_SPEND_CAP_USD`. To check
the current month's total without waiting for a refusal:

- The Firestore implementation (OBRA-90) writes per-month totals to
  `rate_limits/{YYYY-MM}/spend`. Until that lands, totals only live in
  memory on the running Cloud Run instance and are visible via the
  per-job log line: `demo job <id> complete cost=$<usd>`.

To force a temporary cap raise (rare):

```bash
gcloud run services update inkwell-demo \
    --project=$GCP_PROJECT_ID --region=$GCP_REGION \
    --update-env-vars=INKWELL_DEMO_MONTHLY_SPEND_CAP_USD=100.0
```

### Manual rollback to a prior revision

```bash
gcloud run revisions list \
    --project=$GCP_PROJECT_ID --region=$GCP_REGION \
    --service=inkwell-demo
gcloud run services update-traffic inkwell-demo \
    --project=$GCP_PROJECT_ID --region=$GCP_REGION \
    --to-revisions=<prior-revision>=100
```

### PR preview deploys

The `demo-deploy` workflow deploys a tagged Cloud Run revision with
**no production traffic** for every PR (gated on `vars.GCP_PROJECT_ID`
being set). The preview URL is posted as a PR comment by the workflow.
Production traffic only shifts after merge to `main`.

## What the demo does NOT do

These are intentional non-features per the OBRA-73 plan:

- Private / authenticated RSS feeds.
- Episodes longer than 30 minutes.
- In-browser interview mode.
- Accounts, saved history, or persisted vault output.
- Mailing list provider integration. Emails sit in Firestore until
  Clara wires the ESP after we have conversion data.
