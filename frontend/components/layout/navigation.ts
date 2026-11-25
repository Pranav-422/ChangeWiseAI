export type NavItem = { href: string; title: string; permission?: string };
export type NavGroup = { zone: string; title: string; items: NavItem[] };

/** Zones are lettered like the border of a drawing sheet. */
export const NAVIGATION: NavGroup[] = [
  { zone: "A", title: "Overview", items: [{ href: "/dashboard", title: "Executive dashboard" }] },
  { zone: "B", title: "Engineering", items: [
    { href: "/engineering-changes", title: "Engineering changes" },
    { href: "/ecn", title: "ECN intake", permission: "VIEW_DOCUMENTS" },
    { href: "/bom", title: "BOM impact" }] },
  { zone: "C", title: "Planning", items: [
    { href: "/inventory", title: "Inventory monitor" },
    { href: "/optimization", title: "Optimization" },
    { href: "/what-if", title: "What-if simulator" }] },
  { zone: "D", title: "Control", items: [
    { href: "/exceptions", title: "Exceptions" },
    { href: "/approvals", title: "Approval center" },
    { href: "/actions", title: "Action tracker" }] },
  { zone: "E", title: "Governance", items: [
    { href: "/audit", title: "Audit history", permission: "VIEW_AUDIT" },
    { href: "/replay", title: "Replay", permission: "VIEW_AUDIT" }] },
  { zone: "F", title: "System", items: [{ href: "/settings", title: "Profile and settings" }] },
];

export function locate(path: string) {
  for (const group of NAVIGATION)
    for (const [index, item] of group.items.entries())
      if (path === item.href || path.startsWith(`${item.href}/`)) return { group, item, ref: `${group.zone}${index + 1}` };
  return null;
}
