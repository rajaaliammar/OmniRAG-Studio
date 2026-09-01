"use client";

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

const HEALTH_VARIANT: Record<
  HealthState,
  "default" | "secondary" | "destructive" | "outline"
> = {
  loading: "secondary",
  healthy: "default",
  degraded: "outline",
  offline: "destructive",
};

/** Top bar with mobile nav toggle and backend health indicator. */
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
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-4 lg:px-6">
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
          <p className="text-sm font-medium">Active collection</p>
          <p className="text-xs text-muted-foreground">{activeCollection}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <div className="hidden text-right sm:block">
          <p className="text-xs text-muted-foreground">Backend</p>
          <p className="font-mono text-xs">{API_BASE_URL}</p>
        </div>
        <Badge variant={HEALTH_VARIANT[healthState]}>
          <span
            className={cn(
              "mr-1.5 inline-block size-2 rounded-full",
              healthState === "healthy" && "bg-emerald-400",
              healthState === "loading" && "animate-pulse bg-muted-foreground",
              healthState === "degraded" && "bg-amber-400",
              healthState === "offline" && "bg-red-400",
            )}
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
          <p className="text-xs text-muted-foreground">{appName || "FastAPI"}</p>
          <p className="text-xs text-muted-foreground">Checked {checkedLabel}</p>
        </div>
      </div>
    </header>
  );
}
