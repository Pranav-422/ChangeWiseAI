"use client";
import type { AuthError } from "@supabase/supabase-js";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { authMessage, safePath } from "@/lib/auth";
import { supabaseBrowser } from "@/lib/supabase/client";
import { Alert, Button, Input } from "@/components/ui/primitives";

function Form() {
  const router = useRouter();
  const query = useSearchParams();
  const [busy, setBusy] = useState<"password" | "guest" | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function enter(how: "password" | "guest", attempt: Promise<{ error: AuthError | null }>) {
    setBusy(how);
    setError(null);
    const { error: problem } = await attempt;
    if (problem) {
      setError(authMessage(problem));
      setBusy(null);
      return;
    }
    router.replace(safePath(query.get("next")));
    router.refresh();
  }
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    void enter("password", supabaseBrowser().auth.signInWithPassword({
      email: String(form.get("email")), password: String(form.get("password")),
    }));
  }
  return (
    <form onSubmit={submit} className="space-y-5">
      {query.get("reason") === "expired" && <Alert kind="warning">Your session ended. Sign in to continue.</Alert>}
      {query.get("reason") === "link" && <Alert kind="warning">That link is no longer valid. Request a new one.</Alert>}
      {error && <Alert kind="critical">{error}</Alert>}
      <Input label="Work email" name="email" type="email" autoComplete="email" required />
      <Input label="Password" name="password" type="password" autoComplete="current-password" required />
      <Button kind="primary" type="submit" busy={busy === "password"} disabled={!!busy} className="w-full">Sign in</Button>
      <Button busy={busy === "guest"} disabled={!!busy} className="w-full" onClick={() => enter("guest", supabaseBrowser().auth.signInAnonymously())}>Continue as guest</Button>
      <p className="text-sm text-ink-2">A guest can view the planning data and change nothing.</p>
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <Link href="/signup" className="font-semibold text-tech hover:underline">Create an account</Link>
        <Link href="/reset-password" className="font-semibold text-tech hover:underline">Forgot your password?</Link>
      </div>
    </form>
  );
}

export default function Login() {
  return (
    <>
      <h1 className="display mb-8 text-5xl">Sign in</h1>
      <Suspense><Form /></Suspense>
    </>
  );
}
