"use client";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { api, type ChangeRow, type Me } from "@/lib/api";
import { useData } from "@/lib/hooks";
import { supabaseBrowser } from "@/lib/supabase/client";
import { Brand } from "./Brand";
import { Rail } from "./Rail";
import { TitleBlock } from "./TitleBlock";
import { Button, ErrorNote, Skeleton } from "@/components/ui/primitives";

type Context = {
  me: Me; can: (permission: string) => boolean;
  changes: ChangeRow[]; change: ChangeRow; scenario: string;
  select: (changeId: string, scenario: string) => void; signOut: () => Promise<void>;
};
const WorkspaceContext = createContext<Context | null>(null);

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace outside the workspace");
  return value;
}

// The selected change survives reloads of this browser only; it is a convenience, not a record.
const STORE = "changewise.selection";
const listeners = new Set<() => void>();
const selection = {
  read: () => { try { return localStorage.getItem(STORE) ?? ""; } catch { return ""; } },
  write: (value: string) => { try { localStorage.setItem(STORE, value); } catch { /* private window */ } listeners.forEach((l) => l()); },
  subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
};

export function Workspace({ children }: { children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const me = useData(["me"], api.me);
  const changes = useData(["changes"], api.changes);
  const stored = useSyncExternalStore(selection.subscribe, selection.read, () => "");
  const [slow, setSlow] = useState(false);
  const [menu, setMenu] = useState(false);
  const waiting = !me.data || !changes.data;

  useEffect(() => {
    if (!waiting) return;
    const timer = setTimeout(() => setSlow(true), 5000);
    return () => clearTimeout(timer);
  }, [waiting]);

  const value = useMemo<Context | null>(() => {
    if (!me.data || !changes.data?.length) return null;
    const [storedChange, storedScenario] = stored.split("|");
    const change = changes.data.find((c) => c.change_id === storedChange) ?? changes.data[0]!;
    const scenario = change.scenarios.some((s) => s.scenario_id === storedScenario) ? storedScenario! : "base";
    const granted = new Set(me.data.permissions);
    return {
      me: me.data, can: (p) => granted.has(p), changes: changes.data, change, scenario,
      select: (c, s) => selection.write(`${c}|${s}`),
      signOut: async () => {
        await supabaseBrowser().auth.signOut();
        router.replace("/login");
        router.refresh();
      },
    };
  }, [me.data, changes.data, stored, router]);

  const error = me.error ?? changes.error;
  if (!value) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-6 p-6">
        <div className="self-start bg-navy-950 p-4"><Brand /></div>
        {error ? (
          <>
            <ErrorNote error={error} retry={() => { void me.mutate(); void changes.mutate(); }} />
            <Button onClick={() => supabaseBrowser().auth.signOut().then(() => router.replace("/login"))} className="self-start">Sign out</Button>
          </>
        ) : changes.data?.length === 0 ? <p>No engineering change is in the database. Load the planning data first.</p> : (
          <div role="status" className="space-y-3">
            <p>{slow ? "Starting the planning service. The first request after a quiet period can take a minute." : "Opening the workspace"}</p>
            <Skeleton className="h-1.5 w-full" />
          </div>
        )}
      </main>
    );
  }
  return (
    <WorkspaceContext.Provider value={value}>
      <a href="#content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-sheet focus:px-4 focus:py-2">Skip to content</a>
      <div className="lg:grid lg:grid-cols-[236px_minmax(0,1fr)]">
        <Rail open={menu} onClose={() => setMenu(false)} />
        <div className="min-w-0">
          <TitleBlock onMenu={() => setMenu(true)} />
          <main id="content" key={path} tabIndex={-1} className="mx-auto max-w-[1480px] animate-enter px-4 pt-8 pb-20 outline-none sm:px-8">{children}</main>
        </div>
      </div>
    </WorkspaceContext.Provider>
  );
}
