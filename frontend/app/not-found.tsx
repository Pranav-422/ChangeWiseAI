import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="mono text-ink-3">404</p>
      <h1 className="display text-4xl">This sheet does not exist</h1>
      <Link href="/dashboard" className="font-semibold text-tech underline">Back to the dashboard</Link>
    </main>
  );
}
