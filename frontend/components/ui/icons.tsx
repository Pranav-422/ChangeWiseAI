import type { SVGProps } from "react";

const PATHS = {
  check: "M4 10.5 8 14.5 16 5.5",
  cross: "M5 5l10 10M15 5 5 15",
  alert: "M10 3 18 17H2L10 3ZM10 8v4M10 14.3v.4",
  clock: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM10 6.5V10l2.5 2",
  dot: "M10 7.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z",
  right: "M8 5l5 5-5 5",
  down: "M5 8l5 5 5-5",
  arrow: "M3 10h13M11.5 5.5 16 10l-4.5 4.5",
  menu: "M3 5.5h14M3 10h14M3 14.5h14",
  search: "M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM13 13l4 4",
  upload: "M10 13V4M6.5 7.5 10 4l3.5 3.5M4 12v4h12v-4",
  file: "M5 2.5h7l3 3v12H5zM12 2.5v3h3",
  shield: "M10 2.5 16 5v4.5c0 4-2.6 6.8-6 8-3.4-1.2-6-4-6-8V5l6-2.5Z",
  user: "M10 3.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM4 17c.6-3.4 3-5 6-5s5.4 1.6 6 5",
  replay: "M4 10a6 6 0 1 1 1.9 4.4M4 10V5.5M4 10h4.4",
  edit: "M4 16l.8-3.4L13 4.4l2.6 2.6-8.2 8.2L4 16Z",
  external: "M8 4H4v12h12v-4M11 4h5v5M16 4l-7 7",
  filter: "M3 5h14M6 10h8M8.5 15h3",
  exit: "M8 4H4v12h4M12 6.5 15.5 10 12 13.5M15.5 10H8",
  spark: "M10 3v5M10 12v5M3 10h5M12 10h5",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16, ...rest }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={1.7}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0" {...rest}>
      <path d={PATHS[name]} />
    </svg>
  );
}
