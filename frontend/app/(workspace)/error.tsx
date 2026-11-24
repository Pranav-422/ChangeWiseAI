"use client";
import { Button } from "@/components/ui/primitives";

export default function WorkspaceError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="border-l-4 border-critical bg-critical-soft p-6">
      <h1 className="display text-2xl">This page stopped working</h1>
      <p className="mt-1 mb-4">No data was changed. Try again, and if it repeats, open another page from the navigation.</p>
      <Button onClick={reset} icon="replay">Try again</Button>
    </div>
  );
}
