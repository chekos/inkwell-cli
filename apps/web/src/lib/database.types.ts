export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type ImportJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type ImportJobStage =
  | "queued"
  | "fetching_source"
  | "extracting_transcript"
  | "generating_notes"
  | "saving_result"
  | "done";

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;
          email: string;
          display_name: string | null;
          created_at: string;
        };
        Insert: {
          id: string;
          email: string;
          display_name?: string | null;
          created_at?: string;
        };
        Update: {
          email?: string;
          display_name?: string | null;
          created_at?: string;
        };
        Relationships: [];
      };
      sources: {
        Row: {
          id: string;
          user_id: string;
          url: string;
          normalized_url: string;
          source_type: string | null;
          title: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          url: string;
          normalized_url: string;
          source_type?: string | null;
          title?: string | null;
          created_at?: string;
        };
        Update: {
          url?: string;
          normalized_url?: string;
          source_type?: string | null;
          title?: string | null;
        };
        Relationships: [];
      };
      import_jobs: {
        Row: {
          id: string;
          user_id: string;
          source_id: string;
          status: ImportJobStatus;
          stage: ImportJobStage | null;
          worker_run_id: string | null;
          error_code: string | null;
          error_message: string | null;
          created_at: string;
          started_at: string | null;
          finished_at: string | null;
        };
        Insert: {
          id?: string;
          user_id: string;
          source_id: string;
          status?: ImportJobStatus;
          stage?: ImportJobStage | null;
          worker_run_id?: string | null;
          error_code?: string | null;
          error_message?: string | null;
          created_at?: string;
          started_at?: string | null;
          finished_at?: string | null;
        };
        Update: {
          source_id?: string;
          status?: ImportJobStatus;
          stage?: ImportJobStage | null;
          worker_run_id?: string | null;
          error_code?: string | null;
          error_message?: string | null;
          started_at?: string | null;
          finished_at?: string | null;
        };
        Relationships: [];
      };
      notes: {
        Row: {
          id: string;
          user_id: string;
          source_id: string;
          import_job_id: string;
          title: string;
          body_markdown: string;
          summary: string | null;
          metadata: Json;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          source_id: string;
          import_job_id: string;
          title: string;
          body_markdown: string;
          summary?: string | null;
          metadata?: Json;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          title?: string;
          body_markdown?: string;
          summary?: string | null;
          metadata?: Json;
          updated_at?: string;
        };
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
}
