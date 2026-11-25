/** Public configuration. Next.js inlines these at build time, so each name must be written out in full. */
export const env = {
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
  supabaseKey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "",
  apiBaseUrl: (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, ""),
};

export const configured = Boolean(env.supabaseUrl && env.supabaseKey && env.apiBaseUrl);
