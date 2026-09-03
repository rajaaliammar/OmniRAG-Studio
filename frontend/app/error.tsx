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
    <html lang="en">
      <body className="flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
        <div className="max-w-md space-y-4 rounded-xl border border-border bg-card p-6 text-center shadow-sm">
          <h2 className="text-lg font-semibold">Something went wrong</h2>
          <p className="text-sm text-muted-foreground">
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
