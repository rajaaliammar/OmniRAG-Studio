"use client";

import { motion } from "motion/react";
import { Menu, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { HealthState } from "@/hooks/use-health";
import { API_BASE_URL } from "@/lib/config";
import { cn } from "@/lib/utils";

type HeaderProps = {
  activeCollection: string;
  healthState: HealthState;
  appName: string;
  lastChecked: Date | null;
  onRefreshHealth: () => void;
  onOpenMobileNav: () => void;
};

const HEALTH_LABEL: Record<HealthState, string> = {
  loading: "Checking…",
  healthy: "Online",
  degraded: "Degraded",
  offline: "Offline",
};

/** Top bar with mobile nav toggle and pulsing backend health indicator. */
export function Header({
  activeCollection,
  healthState,
  appName,
  lastChecked,
  onRefreshHealth,
  onOpenMobileNav,
}: HeaderProps) {
  const checkedLabel = lastChecked
    ? lastChecked.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-zinc-800/80 bg-zinc-950/50 px-4 backdrop-blur-md lg:px-6">
      <div className="flex items-center gap-3">
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          className="lg:hidden"
          onClick={onOpenMobileNav}
          aria-label="Open navigation"
        >
          <Menu className="size-4" />
        </Button>
        <div>
          <p className="text-sm font-medium text-zinc-100">Active collection</p>
          <p className="accent-gradient-text text-xs font-medium">
            {activeCollection}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <div className="hidden text-right sm:block">
          <p className="text-xs text-zinc-500">Backend</p>
          <p className="font-mono text-xs text-zinc-400">{API_BASE_URL}</p>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "border-zinc-700/80 bg-zinc-900/70 px-2.5 py-1 text-zinc-200",
            healthState === "healthy" && "border-emerald-500/40 bg-emerald-500/10",
            healthState === "degraded" && "border-amber-500/40 bg-amber-500/10",
            healthState === "offline" && "border-red-500/40 bg-red-500/10",
          )}
        >
          <motion.span
            className={cn(
              "mr-1.5 inline-block size-2 rounded-full",
              healthState === "healthy" && "glow-online bg-emerald-400",
              healthState === "loading" && "animate-pulse bg-zinc-400",
              healthState === "degraded" && "bg-amber-400",
              healthState === "offline" && "bg-red-400",
            )}
            animate={
              healthState === "healthy"
                ? { scale: [1, 1.15, 1] }
                : { scale: 1 }
            }
            transition={
              healthState === "healthy"
                ? { duration: 2.2, repeat: Infinity, ease: "easeInOut" }
                : undefined
            }
          />
          {HEALTH_LABEL[healthState]}
        </Badge>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={() => void onRefreshHealth()}
          aria-label="Refresh backend health"
        >
          <RefreshCw
            className={cn("size-4", healthState === "loading" && "animate-spin")}
          />
        </Button>
        <div className="hidden text-right md:block">
          <p className="text-xs text-zinc-300">{appName || "FastAPI"}</p>
          <p className="text-xs text-zinc-500">Checked {checkedLabel}</p>
        </div>
      </div>
    </header>
  );
}
