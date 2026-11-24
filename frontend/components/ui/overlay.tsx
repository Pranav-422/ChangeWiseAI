"use client";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Button, IconButton, cx } from "./primitives";

/** Native dialog: focus trap, Escape and inert background come from the platform. */
function Modal({ open, onClose, title, children, className }:
  { open: boolean; onClose: () => void; title: string; children: ReactNode; className: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} aria-labelledby={heading} onClose={onClose} className={className}
      onClick={(e) => e.target === ref.current && onClose()}>
      {open && (
        <div className="flex max-h-full flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-3">
            <h2 id={heading} className="display text-2xl">{title}</h2>
            <IconButton icon="cross" label="Close" onClick={onClose} className="-mr-2" />
          </header>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}

export function Dialog(props: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return <Modal {...props} className="m-auto w-[min(34rem,calc(100vw-2rem))] max-h-[85vh] rounded-soft bg-sheet shadow-drawer" />;
}

export function Drawer(props: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return <Modal {...props} className="m-0 ml-auto h-dvh max-h-dvh w-[min(30rem,100vw)] bg-sheet shadow-drawer open:animate-enter" />;
}

export function Confirm({ open, onClose, onConfirm, title, children, action, danger, busy }: {
  open: boolean; onClose: () => void; onConfirm: () => void; title: string; children: ReactNode; action: string; danger?: boolean; busy?: boolean;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <div className="text-ink-2">{children}</div>
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <Button onClick={onClose}>Go back</Button>
        <Button kind={danger ? "danger" : "primary"} busy={busy} onClick={onConfirm}>{action}</Button>
      </div>
    </Dialog>
  );
}

/** Shows on hover and on keyboard focus of whatever it wraps. */
export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  const id = useId();
  return (
    <span className="group relative inline-flex" aria-describedby={id}>
      {children}
      <span role="tooltip" id={id}
        className="pointer-events-none absolute bottom-full left-1/2 z-40 mb-2 w-max max-w-64 -translate-x-1/2 rounded-sharp bg-navy-900 px-2.5 py-1.5 text-[13px] leading-snug text-white opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        {text}
      </span>
    </span>
  );
}

export function Tabs({ tabs, label }: { tabs: { id: string; title: string; content: ReactNode }[]; label: string }) {
  const [active, setActive] = useState(tabs[0]?.id);
  const base = useId();
  const onKey = (e: KeyboardEvent) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    const index = tabs.findIndex((t) => t.id === active);
    const next = tabs[(index + step + tabs.length) % tabs.length]!;
    setActive(next.id);
    document.getElementById(`${base}-${next.id}`)?.focus();
  };
  return (
    <div>
      <div role="tablist" aria-label={label} onKeyDown={onKey} className="mb-5 flex gap-1 overflow-x-auto border-b border-line-strong">
        {tabs.map((t) => (
          <button key={t.id} id={`${base}-${t.id}`} role="tab" type="button" aria-selected={t.id === active} aria-controls={`${base}-${t.id}-panel`}
            tabIndex={t.id === active ? 0 : -1} onClick={() => setActive(t.id)}
            className={cx("-mb-px min-h-11 border-b-[3px] px-4 text-sm font-semibold whitespace-nowrap transition-colors",
              t.id === active ? "border-tech text-ink" : "border-transparent text-ink-2 hover:text-ink")}>
            {t.title}
          </button>
        ))}
      </div>
      {tabs.map((t) => t.id === active && (
        <div key={t.id} role="tabpanel" id={`${base}-${t.id}-panel`} aria-labelledby={`${base}-${t.id}`} className="animate-enter">{t.content}</div>
      ))}
    </div>
  );
}

/** Button with a list of choices. Closes on Escape, on choosing and on leaving. */
export function Menu({ label, children, className }: { label: ReactNode; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const close = () => ref.current?.removeAttribute("open");
  return (
    <details ref={ref} className={cx("relative", className)} onKeyDown={(e) => e.key === "Escape" && close()}
      onBlur={(e) => !e.currentTarget.contains(e.relatedTarget) && close()}>
      <summary className="list-none rounded-sharp [&::-webkit-details-marker]:hidden">{label}</summary>
      <div onClick={close} className="absolute right-0 z-50 mt-1 min-w-56 rounded-soft bg-sheet p-1 text-ink shadow-menu">{children}</div>
    </details>
  );
}

export function Pager({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  if (total <= limit) return null;
  return (
    <nav aria-label="Pages" className="mt-3 flex items-center justify-between gap-3 text-sm">
      <span className="num text-ink-2">{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
      <div className="flex gap-2">
        <Button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</Button>
        <Button disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</Button>
      </div>
    </nav>
  );
}
