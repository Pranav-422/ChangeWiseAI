import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { configured, env } from "@/lib/env";

const PUBLIC = ["/login", "/signup", "/reset-password", "/auth"];

/** Refreshes the Supabase session and keeps signed-out visitors out of the workspace. */
export async function proxy(request: NextRequest) {
  if (!configured) return NextResponse.next();
  let response = NextResponse.next({ request });
  const supabase = createServerClient(env.supabaseUrl, env.supabaseKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (items) => {
        items.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        items.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });
  const { data } = await supabase.auth.getClaims(); // verifies the signature; getSession() would not
  const path = request.nextUrl.pathname;
  const open = PUBLIC.some((p) => path === p || path.startsWith(`${p}/`));
  if (!data?.claims && !open) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = path === "/" ? "" : `?next=${encodeURIComponent(path)}`;
    const redirect = NextResponse.redirect(url);
    response.cookies.getAll().forEach((c) => redirect.cookies.set(c));
    return redirect;
  }
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = { matcher: ["/((?!_next/|favicon.ico|icon.svg|.*\\.(?:png|svg|woff2?)$).*)"] };
