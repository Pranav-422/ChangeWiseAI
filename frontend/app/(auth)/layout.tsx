import type { ReactNode } from "react";
import { Brand } from "@/components/layout/Brand";

/** Left: the sheet this product works on. Right: the form. */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <div className="on-navy relative hidden flex-col justify-between overflow-hidden bg-navy-950 p-12 text-white lg:flex">
        <div aria-hidden className="drafting absolute inset-0 opacity-70" />
        <div className="relative"><Brand /></div>
        <svg viewBox="0 0 640 300" aria-hidden className="relative w-full max-w-2xl self-center">
          <g fill="none" strokeLinejoin="round">
            <g stroke="#d08a52" strokeWidth={2}>
              <path d="M30 220V90h46v84h120v46Z" /><circle cx={53} cy={118} r={11} /><circle cx={160} cy={197} r={11} /><path d="M76 174l34-84" strokeDasharray="5 5" />
            </g>
            <g stroke="#9fb3c8" strokeWidth={1}>
              <path d="M30 246h166M30 238v16M196 238v16M30 246l8-4v8ZM196 246l-8-4v8Z" />
              <path d="M290 60v190M296 60h64M296 250h64" strokeDasharray="2 6" />
            </g>
            <g stroke="#3ccbee" strokeWidth={2.5}>
              <path d="M410 220V90h46c0 60 24 84 84 84h60v46Z" /><circle cx={433} cy={118} r={11} /><circle cx={560} cy={197} r={11} /><path d="M456 90c0 60 24 84 84 84" strokeWidth={5} opacity={0.35} />
            </g>
            <path d="M222 155h150M358 146l14 9-14 9" stroke="#fff" strokeWidth={2} />
          </g>
          <g fontFamily="var(--font-mono)" fontSize={14} fill="#9fb3c8">
            <text x={94} y={272}>166.0</text><text x={30} y={72} fill="#d08a52">REV B</text><text x={410} y={72} fill="#3ccbee">REV C</text><text x={240} y={140} fill="#fff">W5 to W6</text>
          </g>
        </svg>
        <p className="display relative max-w-lg text-[44px]">Move from one revision to the next without stopping the line.</p>
      </div>
      <main className="flex flex-col justify-center px-6 py-12 sm:px-16">
        <div className="mb-10 self-start bg-navy-950 p-3 lg:hidden"><Brand /></div>
        <div className="w-full max-w-md">{children}</div>
      </main>
    </div>
  );
}
