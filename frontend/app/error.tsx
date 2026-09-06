"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen items-center justify-center bg-zinc-950 px-4 text-zinc-100">
        <div className="glass-panel max-w-md space-y-4 rounded-2xl p-6 text-center shadow-2xl">
          <h2 className="font-heading text-lg font-semibold">Something went wrong</h2>
          <p className="text-sm text-zinc-400">
            The page hit an unexpected frontend error. Retry to restore the app.
          </p>
          <Button type="button" onClick={reset}>
            Try again
          </Button>
        </div>
      </body>
    </html>
  );
}
