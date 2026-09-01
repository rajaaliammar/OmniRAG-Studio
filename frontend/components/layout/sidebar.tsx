"use client";

import {
  Database,
  FolderOpen,
  LayoutDashboard,
  MessageSquare,
  Plus,
  Upload,
} from "lucide-react";

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

/** Left navigation rail with collection management. */
export function Sidebar({
  collections,
  activeCollection,
  onSelectCollection,
  onAddCollection,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const handleCreateCollection = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const name = String(formData.get("collectionName") ?? "");
    onAddCollection(name);
    event.currentTarget.reset();
  };

  return (
    <>
      <div
        aria-hidden={!mobileOpen}
        className={cn(
          "fixed inset-0 z-40 bg-black/40 transition-opacity lg:hidden",
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onCloseMobile}
      />
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-2 border-b border-sidebar-border px-4 py-4">
          <div className="flex size-9 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
            <Database className="size-4" />
          </div>
          <div>
            <p className="text-sm font-semibold">OmniRAG Studio</p>
            <p className="text-xs text-muted-foreground">Collection workspace</p>
          </div>
        </div>

        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-1">
            {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                onClick={onCloseMobile}
              >
                <Icon className="size-4" />
                {label}
              </button>
            ))}
          </nav>

          <Separator className="my-4" />

          <div className="space-y-3">
            <div className="flex items-center gap-2 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <FolderOpen className="size-3.5" />
              Collections
            </div>
            <div className="space-y-1">
              {collections.map((collection) => (
                <button
                  key={collection}
                  type="button"
                  onClick={() => {
                    onSelectCollection(collection);
                    onCloseMobile();
                  }}
                  className={cn(
                    "flex w-full items-center rounded-lg px-3 py-2 text-left text-sm transition-colors",
                    collection === activeCollection
                      ? "bg-sidebar-primary text-sidebar-primary-foreground"
                      : "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  )}
                >
                  {collection}
                </button>
              ))}
            </div>
            <form
              className="flex items-center gap-2 px-1"
              onSubmit={handleCreateCollection}
            >
              <Input
                name="collectionName"
                placeholder="New collection"
                className="h-8 bg-background"
                aria-label="New collection name"
              />
              <Button type="submit" size="icon-sm" variant="outline">
                <Plus className="size-4" />
              </Button>
            </form>
          </div>
        </ScrollArea>
      </aside>
    </>
  );
}
