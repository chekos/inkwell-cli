import { NextResponse } from "next/server";

import type { Database } from "@/lib/database.types";
import { requireServerSupabaseClient } from "@/lib/supabase/server";

type JobStatusPayload = Pick<
  Database["public"]["Tables"]["import_jobs"]["Row"],
  "id" | "status" | "stage" | "error_code" | "error_message" | "finished_at"
>;
type JobNotePayload = Pick<Database["public"]["Tables"]["notes"]["Row"], "id">;

export async function GET(_request: Request, context: RouteContext<"/api/jobs/[id]">) {
  const { id } = await context.params;
  const supabase = await requireServerSupabaseClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Sign in to view jobs." }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("import_jobs")
    .select("id,status,stage,error_code,error_message,finished_at")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();

  if (error || !data) {
    return NextResponse.json({ error: "Job not found." }, { status: 404 });
  }

  const job = data as JobStatusPayload;

  const { data: note } = await supabase
    .from("notes")
    .select("id")
    .eq("import_job_id", id)
    .eq("user_id", user.id)
    .maybeSingle();

  const jobNote = note as JobNotePayload | null;

  return NextResponse.json({
    status: job.status,
    stage: job.stage,
    noteId: jobNote?.id ?? null,
    error:
      job.status === "failed"
        ? {
            code: job.error_code,
            message: job.error_message,
          }
        : null,
  });
}
