"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { authMessage } from "@/lib/auth";
import { supabaseBrowser } from "@/lib/supabase/client";
import { Alert, Button, Input } from "@/components/ui/primitives";

export default function ResetPassword() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const email = String(new FormData(e.currentTarget).get("email"));
    const { error: problem } = await supabaseBrowser().auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/confirm?next=/update-password`,
    });
    setBusy(false);
    if (problem) setError(authMessage(problem));
    else setSent(true);
  }
  return (
    <>
      <h1 className="display mb-8 text-5xl">Reset your password</h1>
      {sent ? <Alert kind="done" title="Request received">If an account uses that address, a reset link is on its way.</Alert> : (
        <form onSubmit={submit} className="space-y-5">
          {error && <Alert kind="critical">{error}</Alert>}
          <Input label="Work email" name="email" type="email" autoComplete="email" required />
          <Button kind="primary" type="submit" busy={busy} className="w-full">Send reset link</Button>
        </form>
      )}
      <p className="mt-6 text-sm"><Link href="/login" className="font-semibold text-tech hover:underline">Back to sign in</Link></p>
    </>
  );
}
