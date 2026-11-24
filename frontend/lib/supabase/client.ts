import { createBrowserClient } from "@supabase/ssr";
import { env } from "@/lib/env";

/** Browser client. @supabase/ssr returns the same instance on every call. */
export function supabaseBrowser() {
  return createBrowserClient(env.supabaseUrl, env.supabaseKey);
}
