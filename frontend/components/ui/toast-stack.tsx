"use client";

import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { useEffect } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ToastMessage = {
  id: string;
  title: string;
  description: string;
  tone: "success" | "error";
};

type ToastStackProps = {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
};

/** Lightweight toast stack for transient ingestion feedback. */
export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  useEffect(() => {
    const timers = toasts.map((toast) =>
      window.setTimeout(() => onDismiss(toast.id), 5000),
    );
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [onDismiss, toasts]);

  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-3">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "pointer-events-auto rounded-xl border bg-background p-4 shadow-lg",
            toast.tone === "success"
              ? "border-emerald-200"
              : "border-destructive/30",
          )}
        >
          <div className="flex items-start gap-3">
            <div className="mt-0.5">
              {toast.tone === "success" ? (
                <CheckCircle2 className="size-5 text-emerald-600" />
              ) : (
                <CircleAlert className="size-5 text-destructive" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">{toast.title}</p>
                <Badge variant={toast.tone === "success" ? "secondary" : "destructive"}>
                  {toast.tone}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {toast.description}
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="-mr-1"
              onClick={() => onDismiss(toast.id)}
              aria-label="Dismiss notification"
            >
              <X className="size-4" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
