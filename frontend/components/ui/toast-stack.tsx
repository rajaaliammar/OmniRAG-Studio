"use client";

import { AnimatePresence, motion } from "motion/react";
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
      <AnimatePresence initial={false}>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.22 }}
            className={cn(
              "pointer-events-auto glass-panel rounded-2xl p-4 shadow-2xl",
              toast.tone === "success"
                ? "border-emerald-500/30"
                : "border-red-500/30",
            )}
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                {toast.tone === "success" ? (
                  <CheckCircle2 className="size-5 text-emerald-400" />
                ) : (
                  <CircleAlert className="size-5 text-red-300" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-zinc-100">{toast.title}</p>
                  <Badge
                    variant={toast.tone === "success" ? "secondary" : "destructive"}
                    className={
                      toast.tone === "success"
                        ? "bg-emerald-500/15 text-emerald-200"
                        : undefined
                    }
                  >
                    {toast.tone}
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-zinc-400">{toast.description}</p>
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
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
