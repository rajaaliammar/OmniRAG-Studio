"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchHealth } from "@/lib/api";

export type HealthState = "loading" | "healthy" | "degraded" | "offline";

const DEFAULT_POLL_MS = 30_000;

async function readHealth(): Promise<{
  state: HealthState;
  appName: string;
}> {
  try {
    const data = await fetchHealth();
    return {
      state: data.status === "ok" ? "healthy" : "degraded",
      appName: data.app,
    };
  } catch {
    return { state: "offline", appName: "" };
  }
}

/** Poll the FastAPI health endpoint and expose connection status. */
export function useHealth(pollMs: number = DEFAULT_POLL_MS) {
  const [state, setState] = useState<HealthState>("loading");
  const [appName, setAppName] = useState("");
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const applyHealth = useCallback(
    (next: { state: HealthState; appName: string }) => {
      setState(next.state);
      setAppName(next.appName);
      setLastChecked(new Date());
    },
    [],
  );

  const refresh = useCallback(async () => {
    const next = await readHealth();
    applyHealth(next);
  }, [applyHealth]);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      const next = await readHealth();
      if (!cancelled) {
        applyHealth(next);
      }
    };

    void poll();
    const timer = window.setInterval(() => void poll(), pollMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [applyHealth, pollMs]);

  return { state, appName, lastChecked, refresh };
}
