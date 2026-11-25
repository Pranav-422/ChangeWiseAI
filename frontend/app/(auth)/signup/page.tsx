"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { authMessage } from "@/lib/auth";
import { supabaseBrowser } from "@/lib/supabase/client";
import { Alert, Button, Input } from "@/components/ui/primitives";

export default function Signup() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email"));
    setBusy(true);
    setError(null);
    const { data, error: problem } = await supabaseBrowser().auth.signUp({
      email, password: String(form.get("password")),
      options: { data: { full_name: String(form.get("name")).trim() }, emailRedirectTo: `${window.location.origin}/auth/confirm?next=/dashboard` },
    });
    setBusy(false);
    if (problem) setError(authMessage(problem));
    else if (data.session) {
      router.replace("/dashboard");
      router.refresh();
    } else setSent(email);
  }
  if (sent) {
    return (
      <>
        <h1 className="display mb-4 text-5xl">Check your inbox</h1>
        <p>A confirmation link was sent to <strong>{sent}</strong>. Open it on this computer to finish.</p>
      </>
    );
  }
  return (
    <>
      <h1 className="display mb-3 text-5xl">Create an account</h1>
      <p className="mb-8 text-ink-2">New accounts can read. An administrator gives you the role you work in.</p>
      <form onSubmit={submit} className="space-y-5">
        {error && <Alert kind="critical">{error}</Alert>}
        <Input label="Full name" name="name" autoComplete="name" required maxLength={120} />
        <Input label="Work email" name="email" type="email" autoComplete="email" required />
        <Input label="Password" name="password" type="password" autoComplete="new-password" required minLength={8} hint="At least 8 characters." />
        <Button kind="primary" type="submit" busy={busy} className="w-full">Create account</Button>
        <p className="text-sm">Already have one? <Link href="/login" className="font-semibold text-tech hover:underline">Sign in</Link></p>
      </form>
    </>
  );
}
