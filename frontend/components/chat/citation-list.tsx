"use client";

import { motion } from "motion/react";

import type { ChatCitation } from "@/lib/api";
import { cn } from "@/lib/utils";

type CitationListProps = {
  citations: ChatCitation[];
};

type SourceChip = {
  key: string;
  label: string;
  fullSource: string;
  href: string | null;
  kind: "file" | "web";
  detail: string;
};

function basenameFromPath(source: string): string {
  const cleaned = source.replace(/\\/g, "/");
  const parts = cleaned.split("/").filter(Boolean);
  return parts[parts.length - 1] || source;
}

function domainFromUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./, "");
    const path = parsed.pathname.replace(/\/+$/, "");
    if (!path || path === "/") {
      return host;
    }
    const shortPath = path.length > 36 ? `${path.slice(0, 33)}…` : path;
    return `${host}${shortPath}`;
  } catch {
    return basenameFromPath(url);
  }
}

function toSourceChip(citation: ChatCitation, index: number): SourceChip {
  const source = (citation.source || "").trim() || "unknown";
  const locator = citation["page/row"] || "";
  const isWeb =
    source.startsWith("http://") ||
    source.startsWith("https://") ||
    source.toLowerCase().includes("github.com");

  const detailParts = [source];
  if (locator && locator !== source) {
    detailParts.push(`Ref: ${locator}`);
  }

  if (isWeb) {
    const href = source.startsWith("http") ? source : `https://${source}`;
    return {
      key: `${source}-${index}`,
      label: domainFromUrl(href),
      fullSource: source,
      href,
      kind: "web",
      detail: detailParts.join(" · "),
    };
  }

  return {
    key: `${source}-${index}`,
    label: basenameFromPath(source),
    fullSource: source,
    href: null,
    kind: "file",
    detail: detailParts.join(" · "),
  };
}

/** Compact Gemini-style source chips with hover tooltips (no raw previews). */
export function CitationList({ citations }: CitationListProps) {
  if (!citations.length) {
    return null;
  }

  const chips: SourceChip[] = [];
  const seen = new Set<string>();
  for (const [index, citation] of citations.entries()) {
    const chip = toSourceChip(citation, index);
    const dedupeKey = chip.label.toLowerCase();
    if (seen.has(dedupeKey)) {
      continue;
    }
    seen.add(dedupeKey);
    chips.push(chip);
  }

  if (!chips.length) {
    return null;
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5">
      <span className="sr-only">Sources</span>
      {chips.map((chip, index) => {
        const icon = chip.kind === "web" ? "🔗" : "📄";
        const className = cn(
          "chip-shimmer group relative inline-flex max-w-full items-center gap-1 rounded-full",
          "border border-slate-700/70 bg-slate-950/55 px-2.5 py-1 text-[11px] leading-none text-slate-300",
          "transition-all duration-300 hover:scale-[1.02] hover:border-cyan-400/45 hover:bg-slate-900/80 hover:text-slate-50",
          "hover:shadow-[0_0_18px_rgba(6,182,212,0.22)]",
        );

        const tooltip = (
          <span
            role="tooltip"
            className="pointer-events-none absolute bottom-[calc(100%+8px)] left-1/2 z-20 hidden w-max max-w-[16rem] -translate-x-1/2 rounded-lg border border-slate-700/80 bg-slate-950/95 px-2.5 py-1.5 text-[10px] leading-snug text-slate-300 opacity-0 shadow-xl backdrop-blur-md transition-opacity duration-300 group-hover:block group-hover:opacity-100 group-focus-visible:block group-focus-visible:opacity-100"
          >
            {chip.detail}
          </span>
        );

        if (chip.href) {
          return (
            <motion.a
              key={chip.key}
              href={chip.href}
              target="_blank"
              rel="noreferrer noopener"
              title={chip.detail}
              className={className}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.04, duration: 0.2 }}
            >
              <span aria-hidden="true">{icon}</span>
              <span className="truncate font-medium">{chip.label}</span>
              {tooltip}
            </motion.a>
          );
        }

        return (
          <motion.span
            key={chip.key}
            title={chip.detail}
            tabIndex={0}
            className={className}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04, duration: 0.2 }}
          >
            <span aria-hidden="true">{icon}</span>
            <span className="truncate font-medium">{chip.label}</span>
            {tooltip}
          </motion.span>
        );
      })}
    </div>
  );
}
