"use client";

import type { ChatCitation } from "@/lib/api";
import { cn } from "@/lib/utils";

type CitationListProps = {
  citations: ChatCitation[];
};

type SourceChip = {
  key: string;
  label: string;
  href: string | null;
  kind: "file" | "web";
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
  const isWeb =
    source.startsWith("http://") ||
    source.startsWith("https://") ||
    source.toLowerCase().includes("github.com");

  if (isWeb) {
    const href = source.startsWith("http") ? source : `https://${source}`;
    return {
      key: `${source}-${index}`,
      label: domainFromUrl(href),
      href,
      kind: "web",
    };
  }

  return {
    key: `${source}-${index}`,
    label: basenameFromPath(source),
    href: null,
    kind: "file",
  };
}

/** Compact Gemini-style source chips — name/domain only, no raw previews. */
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
      {chips.map((chip) => {
        const icon = chip.kind === "web" ? "🔗" : "📄";
        const className = cn(
          "inline-flex max-w-full items-center gap-1 rounded-full border border-border/70",
          "bg-muted/40 px-2.5 py-1 text-[11px] leading-none text-muted-foreground",
          "transition-colors hover:border-border hover:bg-muted hover:text-foreground",
        );

        if (chip.href) {
          return (
            <a
              key={chip.key}
              href={chip.href}
              target="_blank"
              rel="noreferrer noopener"
              title={chip.href}
              className={className}
            >
              <span aria-hidden="true">{icon}</span>
              <span className="truncate font-medium">{chip.label}</span>
            </a>
          );
        }

        return (
          <span key={chip.key} title={chip.label} className={className}>
            <span aria-hidden="true">{icon}</span>
            <span className="truncate font-medium">{chip.label}</span>
          </span>
        );
      })}
    </div>
  );
}
