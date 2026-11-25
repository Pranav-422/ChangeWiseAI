/** Two revision triangles overlapping: the outgoing one drawn, the incoming one solid. */
export function Brand({ compact }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-3">
      <svg viewBox="0 0 34 24" width={38} height={27} aria-hidden>
        <path d="M2 22 11 4l9 18Z" fill="none" stroke="#d08a52" strokeWidth={2} strokeLinejoin="round" />
        <path d="M14 22 23 4l9 18Z" fill="var(--color-signal)" stroke="var(--color-signal)" strokeWidth={2} strokeLinejoin="round" />
      </svg>
      {!compact && <span className="display text-[21px] tracking-wide text-white">CHANGEWISE <span className="text-signal">AI</span></span>}
      {compact && <span className="sr-only">ChangeWise AI</span>}
    </span>
  );
}
