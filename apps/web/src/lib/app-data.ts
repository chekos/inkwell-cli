import { createServerSupabaseClient } from "@/lib/supabase/server";
import type { Database } from "@/lib/database.types";

type ImportJobRow = Database["public"]["Tables"]["import_jobs"]["Row"];
type NoteRow = Database["public"]["Tables"]["notes"]["Row"];
type DashboardJob = Pick<
  ImportJobRow,
  "id" | "status" | "stage" | "error_message" | "created_at" | "finished_at"
>;
type DashboardNote = Pick<NoteRow, "id" | "title" | "summary" | "created_at" | "source_id">;
export type LibraryNote = Pick<
  NoteRow,
  "id" | "title" | "summary" | "created_at" | "updated_at"
>;
type JobDetail = Pick<
  ImportJobRow,
  | "id"
  | "status"
  | "stage"
  | "error_code"
  | "error_message"
  | "created_at"
  | "started_at"
  | "finished_at"
  | "source_id"
>;
type NoteDetail = Pick<
  NoteRow,
  | "id"
  | "title"
  | "body_markdown"
  | "summary"
  | "metadata"
  | "created_at"
  | "updated_at"
  | "source_id"
  | "import_job_id"
>;
type JobNote = Pick<NoteRow, "id">;

export async function getCurrentUser() {
  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return null;
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}

export async function getDashboardData() {
  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return { configured: false as const, notes: [], jobs: [] };
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return { configured: true as const, notes: [], jobs: [] };
  }

  const [notesResult, jobsResult] = await Promise.all([
    supabase
      .from("notes")
      .select("id,title,summary,created_at,source_id")
      .order("created_at", { ascending: false })
      .limit(5),
    supabase
      .from("import_jobs")
      .select("id,status,stage,error_message,created_at,finished_at")
      .order("created_at", { ascending: false })
      .limit(5),
  ]);

  return {
    configured: true as const,
    notes: (notesResult.data ?? []) as DashboardNote[],
    jobs: (jobsResult.data ?? []) as DashboardJob[],
  };
}

export async function getLibraryData() {
  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return { configured: false as const, notes: [], jobs: [] };
  }

  const [notesResult, jobsResult] = await Promise.all([
    supabase
      .from("notes")
      .select("id,title,summary,created_at,updated_at")
      .order("created_at", { ascending: false }),
    supabase
      .from("import_jobs")
      .select("id,status,stage,error_message,created_at,finished_at")
      .neq("status", "succeeded")
      .order("created_at", { ascending: false }),
  ]);

  return {
    configured: true as const,
    notes: (notesResult.data ?? []) as LibraryNote[],
    jobs: (jobsResult.data ?? []) as DashboardJob[],
  };
}

export async function getJob(id: string) {
  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return null;
  }

  const { data } = await supabase
    .from("import_jobs")
    .select("id,status,stage,error_code,error_message,created_at,started_at,finished_at,source_id")
    .eq("id", id)
    .single();

  return data as JobDetail | null;
}

export async function getJobNote(id: string) {
  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return null;
  }

  const { data } = await supabase
    .from("notes")
    .select("id")
    .eq("import_job_id", id)
    .maybeSingle();

  return data as JobNote | null;
}

export async function getNote(id: string) {
  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return null;
  }

  const { data } = await supabase
    .from("notes")
    .select("id,title,body_markdown,summary,metadata,created_at,updated_at,source_id,import_job_id")
    .eq("id", id)
    .single();

  return data as NoteDetail | null;
}
