"use client";

import { useState } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { IngestionPanel } from "@/components/ingestion/ingestion-panel";
import { useCollections } from "@/hooks/use-collections";
import { useHealth } from "@/hooks/use-health";

/** Responsive dashboard shell: sidebar, header, split main viewport. */
export function DashboardShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { state, appName, lastChecked, refresh } = useHealth();
  const {
    collections,
    activeCollection,
    setActiveCollection,
    addCollection,
  } = useCollections();

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        collections={collections}
        activeCollection={activeCollection}
        onSelectCollection={setActiveCollection}
        onAddCollection={addCollection}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <Header
          activeCollection={activeCollection}
          healthState={state}
          appName={appName}
          lastChecked={lastChecked}
          onRefreshHealth={refresh}
          onOpenMobileNav={() => setMobileOpen(true)}
        />

        <main className="grid min-h-0 flex-1 gap-4 p-4 lg:grid-cols-2 lg:p-6">
          <IngestionPanel collectionName={activeCollection} />
          <ChatPanel collectionName={activeCollection} />
        </main>
      </div>
    </div>
  );
}
