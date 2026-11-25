const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const plain = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });
const when = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const dayOnly = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });

type Maybe = number | null | undefined;
const NONE = "–";

export const inr = (n: Maybe) => (n == null ? NONE : rupees.format(n));
export const qty = (n: Maybe) => (n == null ? NONE : plain.format(n));
export const week = (n: Maybe) => (n == null ? NONE : `W${n}`);
export const signed = (n: Maybe, format: (v: number) => string = qty) =>
  n == null ? NONE : n === 0 ? "no change" : `${n > 0 ? "+" : "−"}${format(Math.abs(n))}`;
export const dateTime = (iso: string | null | undefined) => (iso ? when.format(new Date(iso)) : NONE);
export const day = (iso: string) => dayOnly.format(new Date(iso));
export const units = (n: Maybe) => (n == null ? NONE : `${qty(n)} ${n === 1 ? "unit" : "units"}`);

/** PRODUCTION_SHORTAGE -> Production shortage; Rev B keeps its capital. */
export function words(code: string | null | undefined) {
  if (!code) return NONE;
  const text = code.replaceAll("_", " ").toLowerCase();
  return (text.charAt(0).toUpperCase() + text.slice(1))
    .replace(/\brev ([a-z])\b/gi, (_, r) => `Rev ${r.toUpperCase()}`)
    .replace(/\b(ecn|bom|po|ai)\b/gi, (m) => m.toUpperCase());
}

export const bytes = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${Math.round(n / 1024)} KB` : `${(n / 1048576).toFixed(1)} MB`);

/** W3, W4, W5, W8 -> W3–W5, W8 */
export function weekRange(list: number[]) {
  const parts: string[] = [];
  for (let i = 0; i < list.length; ) {
    let j = i;
    while (list[j + 1] === list[j]! + 1) j++;
    parts.push(i === j ? `W${list[i]}` : `W${list[i]}–W${list[j]}`);
    i = j + 1;
  }
  return parts.join(", ");
}

const ROLES: Record<string, string> = {
  ADMIN: "Administrator", ENGINEERING: "Engineering", PURCHASING: "Purchasing",
  PRODUCTION_PLANNER: "Production planner", QUALITY: "Quality", VIEWER: "Viewer",
};
export const roleName = (role: string) => ROLES[role] ?? words(role);
