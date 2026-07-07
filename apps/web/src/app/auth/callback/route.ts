import { NextResponse, type NextRequest } from "next/server";

import { redirectToLoginWithError, sanitizeRedirectPath } from "@/lib/auth-redirect";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");
  const next = sanitizeRedirectPath(requestUrl.searchParams.get("next"));

  if (requestUrl.searchParams.has("error") || requestUrl.searchParams.has("error_code")) {
    return redirectToLoginWithError(request, "callback_error");
  }

  if (!code) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    return redirectToLoginWithError(request, "auth_callback_failed");
  }

  return NextResponse.redirect(new URL(next, request.url));
}
