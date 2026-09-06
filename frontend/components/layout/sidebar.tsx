"use client";

import { AnimatePresence, motion } from "motion/react";
import {
  Database,
  FolderOpen,
  LayoutDashboard,
  MessageSquare,
  Plus,
  Upload,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

type SidebarProps = {
  collections: string[];
  activeCollection: string;
  onSelectCollection: (name: string) => void;
  onAddCollection: (name: string) => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
};

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "ingest", label: "Ingestion", icon: Upload },
  { id: "chat", label: "Chat", icon: MessageSquare },
] as const;

/** Left navigation rail with collection management and animated active states. */
export function Sidebar({
  collections,
  activeCollection,
  onSelectCollection,
  onAddCollection,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const [activeNav, setActiveNav] = useState<(typeof NAV_ITEMS)[number]["id"]>(
    "dashboard",
  );

  const handleCreateCollection = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const name = String(formData.get("collectionName") ?? "");
    onAddCollection(name);
    event.currentTarget.reset();
  };

  return (
    <>
      <AnimatePresence>
        {mobileOpen ? (
          <motion.div
            key="sidebar-overlay"
            aria-hidden
            className="fixed inset-0 z-40 bg-zinc-950/70 backdrop-blur-sm lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onCloseMobile}
          />
        ) : null}
      </AnimatePresence>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-zinc-800/80 bg-zinc-950/90 text-zinc-100 backdrop-blur-xl lg:static lg:translate-x-0",
        )}
      >
        <div
          className={cn(
            "flex h-full w-72 flex-col transition-transform duration-300 ease-out lg:translate-x-0",
            mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
          )}
        >
          <div className="flex items-center gap-3 border-b border-zinc-800/80 px-4 py-4">
            <div className="flex size-10 items-center justify-center rounded-xl accent-gradient shadow-[0_0_24px_rgba(139,92,246,0.35)]">
              <Database className="size-4 text-white" />
            </div>
            <div>
              <p className="font-heading text-sm font-semibold tracking-tight">
                OmniRAG Studio
              </p>
              <p className="text-xs text-zinc-400">Collection workspace</p>
            </div>
          </div>

          <ScrollArea className="flex-1 px-3 py-4">
            <nav className="relative space-y-1">
              {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
                const isActive = activeNav === id;
                return (
                  <button
                    key={id}
                    type="button"
                    className={cn(
                      "relative flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm transition-colors",
                      isActive
                        ? "text-zinc-50"
                        : "text-zinc-400 hover:bg-zinc-900/70 hover:text-zinc-100",
                    )}
                    onClick={() => {
                      setActiveNav(id);
                      onCloseMobile();
                    }}
                  >
                    {isActive ? (
                      <motion.span
                        layoutId="sidebar-active-tab"
                        className="absolute inset-0 rounded-xl border border-violet-500/30 bg-violet-500/15 shadow-[0_0_20px_rgba(139,92,246,0.15)]"
                        transition={{ type: "spring", stiffness: 420, damping: 34 }}
                      />
                    ) : null}
                    <Icon className="relative z-10 size-4" />
                    <span className="relative z-10">{label}</span>
                  </button>
                );
              })}
            </nav>

            <Separator className="my-4 bg-zinc-800/80" />

            <div className="space-y-3">
              <div className="flex items-center gap-2 px-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                <FolderOpen className="size-3.5" />
                Collections
              </div>
              <div className="space-y-1">
                {collections.map((collection) => {
                  const isActive = collection === activeCollection;
                  return (
                    <button
                      key={collection}
                      type="button"
                      onClick={() => {
                        onSelectCollection(collection);
                        onCloseMobile();
                      }}
                      className={cn(
                        "relative flex w-full items-center rounded-xl px-3 py-2 text-left text-sm transition-colors",
                        isActive
                          ? "text-zinc-50"
                          : "text-zinc-400 hover:bg-zinc-900/70 hover:text-zinc-100",
                      )}
                    >
                      {isActive ? (
                        <motion.span
                          layoutId="sidebar-active-collection"
                          className="absolute inset-0 rounded-xl accent-gradient opacity-90"
                          transition={{ type: "spring", stiffness: 420, damping: 34 }}
                        />
                      ) : null}
                      <span className="relative z-10 truncate">{collection}</span>
                    </button>
                  );
                })}
              </div>
              <form
                className="flex items-center gap-2 px-1"
                onSubmit={handleCreateCollection}
              >
                <Input
                  name="collectionName"
                  placeholder="New collection"
                  className="h-9 bg-zinc-950/70"
                  aria-label="New collection name"
                />
                <Button type="submit" size="icon-sm" variant="outline">
                  <Plus className="size-4" />
                </Button>
              </form>
            </div>
          </ScrollArea>
        </div>
      </aside>
    </>
  );
}
