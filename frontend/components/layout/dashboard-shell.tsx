"use client";

import { motion } from "motion/react";
import { useState } from "react";

import { AmbientBackground } from "@/components/layout/ambient-background";
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
    <div className="relative flex min-h-screen bg-transparent text-slate-100">
      <AmbientBackground />

      <Sidebar
        collections={collections}
        activeCollection={activeCollection}
        onSelectCollection={setActiveCollection}
        onAddCollection={addCollection}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="relative z-10 flex min-h-screen min-w-0 flex-1 flex-col">
        <Header
          activeCollection={activeCollection}
          healthState={state}
          appName={appName}
          lastChecked={lastChecked}
          onRefreshHealth={refresh}
          onOpenMobileNav={() => setMobileOpen(true)}
        />

        <main className="grid min-h-0 flex-1 gap-4 p-4 lg:grid-cols-2 lg:gap-6 lg:p-6">
          <motion.div
            className="min-h-0"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
          >
            <ErrorBoundary title="Ingestion module failed">
              <IngestionPanel
                collectionName={activeCollection}
                collections={collections}
                onCollectionSelected={setActiveCollection}
                onCollectionCreated={addCollection}
                onCollectionRefreshed={refreshCollection}
              />
            </ErrorBoundary>
          </motion.div>
          <motion.div
            className="min-h-0"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.06, ease: "easeOut" }}
          >
            <ErrorBoundary title="Chat module failed">
              <ChatPanel collectionName={activeCollection} />
            </ErrorBoundary>
          </motion.div>
        </main>
      </div>
    </div>
  );
}
