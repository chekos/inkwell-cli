import { z } from "zod";

import { dispatchImportJob } from "@/lib/worker-dispatch";
import { requireServerSupabaseClient } from "@/lib/supabase/server";

export const createImportSchema = z.object({
  url: z.string().trim().url().max(4096),
});

export async function createImport(input: unknown) {
  const parsed = createImportSchema.parse(input);
  const supabase = await requireServerSupabaseClient();

  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError || !user) {
    return { ok: false as const, status: 401, error: "Sign in before creating imports." };
  }

  const normalizedUrl = normalizeSourceUrl(parsed.url);

  const { data: source, error: sourceError } = await supabase
    .from("sources")
    .insert({
      user_id: user.id,
      url: parsed.url,
      normalized_url: normalizedUrl,
    })
    .select("id")
    .single();

  if (sourceError || !source) {
    return { ok: false as const, status: 500, error: "Could not save the source." };
  }

  const { data: job, error: jobError } = await supabase
    .from("import_jobs")
    .insert({
      user_id: user.id,
      source_id: source.id,
      status: "queued",
      stage: "queued",
    })
    .select("id")
    .single();

  if (jobError || !job) {
    return { ok: false as const, status: 500, error: "Could not create the import job." };
  }

  const dispatch = await dispatchImportJob({
    jobId: job.id,
    userId: user.id,
    url: parsed.url,
  });

  if (dispatch.workerRunId) {
    await supabase
      .from("import_jobs")
      .update({ worker_run_id: dispatch.workerRunId })
      .eq("id", job.id);
  }

  return {
    ok: true as const,
    jobId: job.id,
    statusUrl: `/app/jobs/${job.id}`,
    dispatched: dispatch.dispatched,
    dispatchReason: dispatch.reason,
  };
}

function normalizeSourceUrl(value: string) {
  const url = new URL(value);
  url.hash = "";
  return url.toString();
}
