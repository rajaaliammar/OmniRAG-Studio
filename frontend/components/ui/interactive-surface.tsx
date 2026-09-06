"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type InteractiveSurfaceProps = React.ComponentProps<"div"> & {
  asChild?: boolean;
};

/**
 * Glass surface with cursor-follow neon lighting.
 * Defaults keep SSR/client markup identical (no hydration mismatch).
 */
export function InteractiveSurface({
  className,
  onMouseMove,
  onMouseLeave,
  ...props
}: InteractiveSurfaceProps) {
  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.currentTarget;
    const rect = target.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    target.style.setProperty("--mx", `${x}%`);
    target.style.setProperty("--my", `${y}%`);
    onMouseMove?.(event);
  };

  const handleMouseLeave = (event: React.MouseEvent<HTMLDivElement>) => {
    event.currentTarget.style.setProperty("--mx", "50%");
    event.currentTarget.style.setProperty("--my", "40%");
    onMouseLeave?.(event);
  };

  return (
    <div
      className={cn("interactive-surface", className)}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      {...props}
    />
  );
}
