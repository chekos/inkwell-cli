import { type EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";

import { redirectToLoginWithError, sanitizeRedirectPath } from "@/lib/auth-redirect";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const tokenHash = requestUrl.searchParams.get("token_hash");
  const type = requestUrl.searchParams.get("type") as EmailOtpType | null;
  const next = sanitizeRedirectPath(requestUrl.searchParams.get("next"));

  if (!tokenHash || !type) {
    return redirectToLoginWithError(request, "auth_confirm_failed");
  }

  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return redirectToLoginWithError(request, "auth_confirm_failed");
  }

  const { error } = await supabase.auth.verifyOtp({
    token_hash: tokenHash,
    type,
  });

  if (error) {
    return redirectToLoginWithError(request, "auth_confirm_failed");
  }

  return NextResponse.redirect(new URL(next, request.url));
}
