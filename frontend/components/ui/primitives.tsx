"use client";
import Link from "next/link";
import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import type { ApiError } from "@/lib/api/errors";
import { Icon, type IconName } from "./icons";

export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");

// Buttons ----------------------------------------------------------------------------------------

const BUTTON = "inline-flex items-center justify-center gap-2 rounded-sharp text-sm font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-45";
const KIND = {
  primary: "min-h-10 px-4 py-2 bg-tech text-white hover:bg-tech-strong active:bg-navy-800",
  dark: "min-h-10 px-4 py-2 bg-navy-900 text-white hover:bg-navy-700",
  outline: "min-h-10 px-4 py-2 border border-line-strong bg-sheet text-ink hover:border-ink hover:bg-sunken",
  danger: "min-h-10 px-4 py-2 border border-critical bg-sheet text-critical hover:bg-critical hover:text-white",
  quiet: "min-h-8 px-2 py-0 text-tech hover:bg-tech-soft",
};
type Kind = keyof typeof KIND;

export function Button({ kind = "outline", busy, icon, children, className, ...rest }:
  { kind?: Kind; busy?: boolean; icon?: IconName } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" {...rest} disabled={rest.disabled || busy} aria-busy={busy || undefined} className={cx(BUTTON, KIND[kind], className)}>
      {busy ? <Spinner /> : icon && <Icon name={icon} />}
      {children}
    </button>
  );
}

export function LinkButton({ href, kind = "outline", icon, children, className }:
  { href: string; kind?: Kind; icon?: IconName; children: ReactNode; className?: string }) {
  return <Link href={href} className={cx(BUTTON, KIND[kind], className)}>{children}{icon && <Icon name={icon} />}</Link>;
}

export function IconButton({ label, icon, className, ...rest }: { label: string; icon: IconName } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" aria-label={label} title={label} {...rest}
      className={cx("inline-flex size-10 items-center justify-center rounded-sharp text-ink-2 hover:bg-neutral-soft hover:text-ink", className)}>
      <Icon name={icon} size={18} />
    </button>
  );
}

export const Spinner = () => (
  <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent" />
);

// Fields -----------------------------------------------------------------------------------------

const INPUT = "w-full min-h-10 rounded-sharp border border-line-strong bg-white px-3 py-2 text-[15px] text-ink placeholder:text-ink-3 hover:border-ink-2 disabled:bg-sunken disabled:text-ink-2 aria-invalid:border-critical";

type FieldProps = { label: string; hint?: ReactNode; error?: string | null; hideLabel?: boolean };

function Field({ label, hint, error, hideLabel, id, children }: FieldProps & { id: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className={hideLabel ? "sr-only" : "mb-1 block text-sm font-semibold"}>{label}</label>
      {children}
      {hint && <p id={`${id}-hint`} className="mt-1 text-[13px] text-ink-3">{hint}</p>}
      {error && <p id={`${id}-error`} className="mt-1 flex items-center gap-1 text-[13px] text-critical"><Icon name="alert" size={14} />{error}</p>}
    </div>
  );
}

function aria(id: string, hint: ReactNode, error?: string | null) {
  return { id, "aria-invalid": error ? true : undefined, "aria-describedby": cx(hint ? `${id}-hint` : null, error ? `${id}-error` : null) || undefined };
}

export function Input({ label, hint, error, hideLabel, className, ...rest }: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return <Field {...{ label, hint, error, hideLabel, id }}><input {...rest} {...aria(id, hint, error)} className={cx(INPUT, className)} /></Field>;
}

export function Textarea({ label, hint, error, hideLabel, className, ...rest }: FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return <Field {...{ label, hint, error, hideLabel, id }}><textarea rows={4} {...rest} {...aria(id, hint, error)} className={cx(INPUT, className)} /></Field>;
}

export function Select({ label, hint, error, hideLabel, className, children, ...rest }: FieldProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  return <Field {...{ label, hint, error, hideLabel, id }}><select {...rest} {...aria(id, hint, error)} className={cx(INPUT, className)}>{children}</select></Field>;
}

// Status -----------------------------------------------------------------------------------------

export type Tone = "critical" | "high" | "pending" | "done" | "active" | "neutral";
const TONE: Record<Tone, string> = {
  critical: "bg-critical-soft text-critical", high: "bg-high-soft text-high", pending: "bg-pending-soft text-pending",
  done: "bg-done-soft text-done", active: "bg-tech-soft text-tech-strong", neutral: "bg-neutral-soft text-ink-2",
};
const TONE_ICON: Record<Tone, IconName> = {
  critical: "alert", high: "alert", pending: "clock", done: "check", active: "dot", neutral: "dot",
};

/** A state is always an icon and a word, never a colour alone. */
export function Status({ tone, children, icon }: { tone: Tone; children: ReactNode; icon?: IconName }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-sharp px-2 py-0.5 text-[13px] font-semibold whitespace-nowrap", TONE[tone])}>
      <Icon name={icon ?? TONE_ICON[tone]} size={13} strokeWidth={2.2} />{children}
    </span>
  );
}

const STATE_TONE: Record<string, Tone> = {
  VALID: "done", CONFIRMED: "done", APPROVED: "done", DONE: "done", RESOLVED: "done", MATCHED: "done", VERIFIED: "done", FEASIBLE: "done",
  NEEDS_REVIEW: "pending", INSUFFICIENT_DATA: "pending", ESCALATED: "pending", OPEN: "pending", AWAITING_REVIEW: "pending", PENDING: "pending",
  INVALID: "critical", REJECTED: "critical", NO_FEASIBLE_PLAN: "critical", INVALID_DATA: "critical", DIFFERENT: "critical", SNAPSHOT_ALTERED: "critical", FAILED: "critical",
  RECOMMENDED: "active", IN_PROGRESS: "active", ACKNOWLEDGED: "active", CRITICAL: "critical", HIGH: "high", MEDIUM: "pending", LOW: "neutral",
};
export const toneOf = (state: string | null | undefined): Tone => STATE_TONE[(state ?? "").toUpperCase()] ?? "neutral";

// Structure --------------------------------------------------------------------------------------

/** A ruled section of the sheet. Not a card: one hairline on top, the reference letter in the corner. */
export function Section({ title, note, action, children, className, id }:
  { title: string; note?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  const heading = useId();
  return (
    <section aria-labelledby={heading} id={id} className={cx("min-w-0 border-t-2 border-ink pt-3", className)}>
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <h2 id={heading} className="display text-[22px]">{title}</h2>
          {note && <p className="mt-1 text-sm text-ink-2">{note}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

export function PageHeading({ title, lead, action }: { title: string; lead?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        <h1 className="display text-[40px] sm:text-[46px]">{title}</h1>
        {lead && <p className="mt-2 text-base text-ink-2">{lead}</p>}
      </div>
      {action && <div className="flex flex-wrap gap-2">{action}</div>}
    </div>
  );
}

export function Metric({ label, value, detail, tone, size = "md" }:
  { label: string; value: ReactNode; detail?: ReactNode; tone?: Tone; size?: "md" | "lg" }) {
  return (
    <div className={cx("border-l-2 pl-3", tone === "critical" ? "border-critical" : tone === "pending" ? "border-pending-mark" : tone === "done" ? "border-done" : "border-line-strong")}>
      <div className="text-sm text-ink-2">{label}</div>
      <div className={cx("display", size === "lg" ? "text-[44px]" : "text-[30px]")}>{value}</div>
      {detail && <div className="mt-0.5 text-sm text-ink-2">{detail}</div>}
    </div>
  );
}

export function Facts({ items, columns = 2 }: { items: [string, ReactNode][]; columns?: 1 | 2 | 3 }) {
  return (
    <dl className={cx("grid gap-x-6 gap-y-3", columns === 3 ? "sm:grid-cols-3" : columns === 2 ? "sm:grid-cols-2" : "")}>
      {items.map(([name, value]) => (
        <div key={name} className="min-w-0">
          <dt className="text-[13px] text-ink-3">{name}</dt>
          <dd className="break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function TableFrame({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="region" aria-label={label} tabIndex={0} className="relative overflow-x-auto border-y border-line bg-sheet">
      <table className="w-full border-collapse text-sm [&_td]:border-t [&_td]:border-line [&_td]:px-3 [&_td]:py-2.5 [&_td]:align-top [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:text-[13px] [&_th]:font-semibold [&_th]:whitespace-nowrap [&_th]:text-ink-2">
        <caption className="sr-only">{label}</caption>
        {children}
      </table>
    </div>
  );
}

// States -----------------------------------------------------------------------------------------

const ALERT: Record<"info" | "warning" | "critical" | "done", [string, IconName]> = {
  info: ["border-tech bg-tech-soft", "dot"], warning: ["border-pending-mark bg-pending-soft", "alert"],
  critical: ["border-critical bg-critical-soft", "alert"], done: ["border-done bg-done-soft", "check"],
};

export function Alert({ kind = "info", title, children, action }: { kind?: keyof typeof ALERT; title?: string; children?: ReactNode; action?: ReactNode }) {
  const [style, icon] = ALERT[kind];
  return (
    <div role={kind === "critical" ? "alert" : "status"} className={cx("flex flex-wrap items-start gap-3 border-l-4 px-4 py-3 text-sm", style)}>
      <Icon name={icon} size={18} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children}
      </div>
      {action}
    </div>
  );
}

export function ErrorNote({ error, retry }: { error: ApiError; retry?: () => void }) {
  const details = error.details as { field?: string; message?: string }[];
  return (
    <Alert kind="critical" title={error.status === 403 ? "Your role does not allow this" : "That did not work"}
      action={retry && <Button onClick={retry} icon="replay">Try again</Button>}>
      <p>{error.message}</p>
      {details.map((d, i) => d.message && <p key={i}>{d.field}: {d.message}</p>)}
      {error.requestId && error.status >= 500 && <p className="mono mt-1 text-ink-2">Reference {error.requestId}</p>}
    </Alert>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="border border-dashed border-line-strong bg-sunken px-6 py-10 text-center">
      <p className="display text-xl">{title}</p>
      {children && <p className="mx-auto mt-2 max-w-prose text-ink-2">{children}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("animate-pulse-line bg-line", className)} />;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="space-y-4">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-10 w-72" />
      <Skeleton className="h-64 w-full" />
      <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-32" /><Skeleton className="h-32" /><Skeleton className="h-32" /></div>
    </div>
  );
}

/** The three states of a read, so no page repeats them. */
export function Loaded<T>({ data, error, retry, children }:
  { data: T | undefined; error: ApiError | undefined; retry?: () => void; children: (data: T) => ReactNode }) {
  if (data !== undefined) return <>{children(data)}</>;
  if (error) return <ErrorNote error={error} retry={retry} />;
  return <Loading />;
}
