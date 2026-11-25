"use client";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { authMessage } from "@/lib/auth";
import { supabaseBrowser } from "@/lib/supabase/client";
import { Alert, Button, Input } from "@/components/ui/primitives";

export default function UpdatePassword() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    if (form.get("password") !== form.get("repeat")) return setError("The two passwords are different.");
    setBusy(true);
    setError(null);
    const { error: problem } = await supabaseBrowser().auth.updateUser({ password: String(form.get("password")) });
    setBusy(false);
    if (problem) return setError(authMessage(problem));
    router.replace("/dashboard");
    router.refresh();
  }
  return (
    <>
      <h1 className="display mb-8 text-5xl">Choose a new password</h1>
      <form onSubmit={submit} className="space-y-5">
        {error && <Alert kind="critical">{error}</Alert>}
        <Input label="New password" name="password" type="password" autoComplete="new-password" required minLength={8} hint="At least 8 characters." />
        <Input label="Repeat the password" name="repeat" type="password" autoComplete="new-password" required minLength={8} />
        <Button kind="primary" type="submit" busy={busy} className="w-full">Save password</Button>
      </form>
    </>
  );
}
