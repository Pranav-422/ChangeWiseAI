import type { EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { safePath } from "@/lib/auth";
import { supabaseServer } from "@/lib/supabase/server";

/** Target of e-mail links: both the token_hash form and the PKCE code form. */
export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams;
  const token = query.get("token_hash"), type = query.get("type") as EmailOtpType | null, code = query.get("code");
  const supabase = await supabaseServer();
  const { error } = token && type
    ? await supabase.auth.verifyOtp({ token_hash: token, type })
    : code ? await supabase.auth.exchangeCodeForSession(code) : { error: new Error("no token") };
  const url = request.nextUrl.clone();
  url.search = "";
  if (error) {
    url.pathname = "/login";
    url.searchParams.set("reason", "link");
  } else {
    url.pathname = type === "recovery" ? "/update-password" : safePath(query.get("next"));
  }
  return NextResponse.redirect(url);
}
