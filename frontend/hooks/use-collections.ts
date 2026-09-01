"use client";

import { useCallback, useState } from "react";

import { DEFAULT_COLLECTION } from "@/lib/config";

/** Local collection list and active selection for Phase 1 shell UI. */
export function useCollections() {
  const [collections, setCollections] = useState<string[]>([
    DEFAULT_COLLECTION,
  ]);
  const [activeCollection, setActiveCollection] =
    useState<string>(DEFAULT_COLLECTION);

  const addCollection = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }
    setCollections((previous) =>
      previous.includes(trimmed)
        ? previous
        : [...previous, trimmed].sort((a, b) => a.localeCompare(b)),
    );
    setActiveCollection(trimmed);
  }, []);

  return {
    collections,
    activeCollection,
    setActiveCollection,
    addCollection,
  };
}
