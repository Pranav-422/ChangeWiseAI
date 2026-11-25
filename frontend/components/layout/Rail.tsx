"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { IconButton, cx } from "@/components/ui/primitives";
import { roleName } from "@/lib/format";
import { Brand } from "./Brand";
import { NAVIGATION } from "./navigation";
import { useWorkspace } from "./Workspace";

/** The sheet's left border: lettered zones, numbered entries. */
export function Rail({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { me, can } = useWorkspace();
  const path = usePathname();
  useEffect(() => {
    if (!open) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open, onClose]);
  return (
    <>
      {open && <button type="button" aria-label="Close navigation" onClick={onClose} className="fixed inset-0 z-40 bg-navy-950/60 lg:hidden" />}
      <div className={cx("on-navy no-print fixed inset-y-0 left-0 z-50 flex w-[272px] flex-col bg-navy-950 text-navy-100 transition-[translate,visibility] duration-200 lg:visible lg:sticky lg:top-0 lg:h-dvh lg:w-auto lg:translate-x-0",
        open ? "visible translate-x-0" : "invisible -translate-x-full")}>
        <div className="flex items-center justify-between px-5 pt-5 pb-4">
          <Link href="/dashboard" onClick={onClose}><Brand /></Link>
          <IconButton icon="cross" label="Close navigation" onClick={onClose} className="text-navy-100 hover:bg-navy-800 hover:text-white lg:hidden" />
        </div>
        <nav aria-label="Main" className="flex-1 overflow-y-auto pb-6">
          {NAVIGATION.map((group) => {
            const items = group.items.map((item, i) => ({ ...item, ref: `${group.zone}${i + 1}` })).filter((i) => !i.permission || can(i.permission));
            if (!items.length) return null;
            return (
              <div key={group.zone} className="border-t border-navy-800 py-2.5">
                <p className="px-5 pb-1 text-[13px] text-navy-300">{group.title}</p>
                <ul>
                  {items.map((item) => {
                    const active = path === item.href || path.startsWith(`${item.href}/`);
                    return (
                      <li key={item.href}>
                        <Link href={item.href} onClick={onClose} aria-current={active ? "page" : undefined}
                          className={cx("group relative flex min-h-9 items-center gap-3 py-1.5 pr-4 pl-5 text-[15px] transition-colors",
                            active ? "bg-navy-800 font-semibold text-white" : "hover:bg-navy-900 hover:text-white")}>
                          {active && <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-signal" />}
                          <span aria-hidden className={cx("mono w-5 text-[11.5px]", active ? "text-signal" : "text-navy-300 group-hover:text-navy-100")}>{item.ref}</span>
                          {item.title}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </nav>
        <div className="border-t border-navy-800 px-5 py-3 text-sm">
          <p className="truncate font-semibold text-white">{me.name}</p>
          <p className="text-navy-300">{roleName(me.role)}</p>
        </div>
      </div>
    </>
  );
}
