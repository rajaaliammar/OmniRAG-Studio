"use client";

import { useCallback, useMemo, useState } from "react";

import { DEFAULT_COLLECTION } from "@/lib/config";

type UseCollectionsResult = {
  collections: string[];
  activeCollection: string;
  setActiveCollection: (name: string) => void;
  addCollection: (name: string) => string | null;
  refreshCollection: (name: string) => string;
};

function normalizeCollectionName(name: string): string {
  const trimmed = name.trim();
  return trimmed || DEFAULT_COLLECTION;
}

/** Local collection list and active selection for dashboard modules. */
export function useCollections(): UseCollectionsResult {
  const [collections, setCollections] = useState<string[]>([
    DEFAULT_COLLECTION,
  ]);
  const [activeCollection, setActiveCollectionState] =
    useState<string>(DEFAULT_COLLECTION);

  const setActiveCollection = useCallback((name: string) => {
    const normalized = normalizeCollectionName(name);
    setActiveCollectionState(normalized);
    setCollections((previous) =>
      previous.includes(normalized)
        ? previous
        : [...previous, normalized].sort((a, b) => a.localeCompare(b)),
    );
  }, []);

  const addCollection = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed) {
      return null;
    }
    setActiveCollection(trimmed);
    return trimmed;
  }, [setActiveCollection]);

  const refreshCollection = useCallback((name: string) => {
    const normalized = normalizeCollectionName(name);
    setCollections((previous) =>
      previous.includes(normalized)
        ? previous
        : [...previous, normalized].sort((a, b) => a.localeCompare(b)),
    );
    return normalized;
  }, []);

  return useMemo(
    () => ({
      collections,
      activeCollection,
      setActiveCollection,
      addCollection,
      refreshCollection,
    }),
    [activeCollection, addCollection, collections, refreshCollection, setActiveCollection],
  );
}
