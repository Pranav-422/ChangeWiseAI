import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { Workspace } from "@/components/layout/Workspace";
import { configured } from "@/lib/env";
import { supabaseServer } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function WorkspaceLayout({ children }: { children: ReactNode }) {
  if (!configured) {
    return (
      <main className="mx-auto max-w-2xl space-y-3 p-10">
        <h1 className="display text-4xl">Not configured yet</h1>
        <p>Set <code className="mono">NEXT_PUBLIC_SUPABASE_URL</code>, <code className="mono">NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY</code> and <code className="mono">NEXT_PUBLIC_API_BASE_URL</code>, then build again.</p>
      </main>
    );
  }
  const { data } = await (await supabaseServer()).auth.getClaims();
  if (!data?.claims) redirect("/login");
  return <Workspace>{children}</Workspace>;
}
