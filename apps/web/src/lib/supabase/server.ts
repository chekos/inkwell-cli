import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import type { Database } from "@/lib/database.types";
import { getSupabasePublicEnv, hasSupabasePublicEnv } from "@/lib/env";

export async function createServerSupabaseClient() {
  if (!hasSupabasePublicEnv()) {
    return null;
  }

  const { url, anonKey } = getSupabasePublicEnv();
  const cookieStore = await cookies();

  return createServerClient<Database>(url, anonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet, headers) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // Server Components cannot always mutate cookies; Proxy refreshes sessions.
        }
        void headers;
      },
    },
  });
}

export async function requireServerSupabaseClient() {
  const supabase = await createServerSupabaseClient();

  if (!supabase) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.",
    );
  }

  return supabase;
}
