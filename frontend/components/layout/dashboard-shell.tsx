"use client";

import { useState } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { IngestionPanel } from "@/components/ingestion/ingestion-panel";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
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
    refreshCollection,
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
          <ErrorBoundary title="Ingestion module failed">
            <IngestionPanel
              collectionName={activeCollection}
              collections={collections}
              onCollectionSelected={setActiveCollection}
              onCollectionCreated={addCollection}
              onCollectionRefreshed={refreshCollection}
            />
          </ErrorBoundary>
          <ErrorBoundary title="Chat module failed">
            <ChatPanel collectionName={activeCollection} />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
