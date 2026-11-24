"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Dialog } from "@/components/ui/overlay";
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/primitives";
import { NAVIGATION } from "./navigation";
import { useWorkspace } from "./Workspace";

/** Ctrl K: go to a page or a change by typing part of its name. */
export function QuickJump() {
  const { can, changes } = useWorkspace();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(true); }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const targets = [
    ...NAVIGATION.flatMap((g) => g.items.filter((i) => !i.permission || can(i.permission)).map((i, n) => ({ href: i.href, title: i.title, note: `${g.zone}${n + 1}` }))),
    ...changes.map((c) => ({ href: `/engineering-changes/${c.change_id}`, title: `${c.change_id}, ${c.reason ?? ""}`, note: "ECN" })),
  ].filter((t) => t.title.toLowerCase().includes(text.trim().toLowerCase()));
  const go = (href: string) => { setOpen(false); setText(""); router.push(href); };
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="flex min-h-10 items-center gap-2 rounded-sharp px-3 text-sm text-ink-2 hover:bg-neutral-soft">
        <Icon name="search" size={17} /><span className="hidden md:block">Go to</span><kbd className="mono hidden border border-line px-1 text-xs lg:block">Ctrl K</kbd>
      </button>
      <Dialog open={open} onClose={() => setOpen(false)} title="Go to">
        <form onSubmit={(e) => { e.preventDefault(); if (targets[0]) go(targets[0].href); }}>
          <Input label="Page or change" hideLabel autoFocus value={text} onChange={(e) => setText(e.target.value)} placeholder="Page or change" />
        </form>
        <ul className="mt-3">
          {targets.map((t) => (
            <li key={t.href}><button type="button" onClick={() => go(t.href)} className="flex min-h-10 w-full items-center gap-3 px-2 text-left hover:bg-tech-soft"><span className="mono w-9 text-xs text-ink-3">{t.note}</span>{t.title}</button></li>
          ))}
          {!targets.length && <li className="py-3 text-ink-2">Nothing matches.</li>}
        </ul>
      </Dialog>
    </>
  );
}
