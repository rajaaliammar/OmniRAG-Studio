"use client";

import { motion } from "motion/react";
import {
  CheckCircle2,
  ChevronDown,
  FileUp,
  Globe,
  LoaderCircle,
  RefreshCcw,
  Table,
  UploadCloud,
  XCircle,
} from "lucide-react";
import {
  useCallback,
  useId,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
} from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { ToastStack, type ToastMessage } from "@/components/ui/toast-stack";
import {
  ingestFile,
  ingestUrl,
  toApiError,
  type IngestResponse,
} from "@/lib/api";
import { DEFAULT_COLLECTION } from "@/lib/config";
import { cn } from "@/lib/utils";

type IngestionPanelProps = {
  collectionName: string;
  collections: string[];
  onCollectionSelected: (name: string) => void;
  onCollectionCreated: (name: string) => string | null;
  onCollectionRefreshed: (name: string) => string;
};

type ActiveMode = "existing" | "new";
type UploadStatus = "idle" | "uploading" | "indexing" | "success" | "error";

type LastResult = {
  source: string;
  chunkCount: number;
  storedCount: number;
  collectionName: string;
  snippets: string[];
} | null;

const ACCEPTED_TYPES = [".pdf", ".csv"];
const MAX_FILE_BYTES = 25 * 1024 * 1024;
const URL_PATTERN = /^https?:\/\/.+/i;

function validateUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return "URL is required.";
  }
  if (!URL_PATTERN.test(trimmed)) {
    return "Enter a valid http:// or https:// URL.";
  }
  try {
    new URL(trimmed);
    return null;
  } catch {
    return "Enter a valid URL.";
  }
}

function validateFile(file: File | null): string | null {
  if (!file) {
    return "Choose a PDF or CSV file to upload.";
  }
  const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!ACCEPTED_TYPES.includes(extension)) {
    return "Only PDF and CSV files are supported.";
  }
  if (file.size === 0) {
    return "The selected file is empty.";
  }
  if (file.size > MAX_FILE_BYTES) {
    return "File exceeds the 25 MB upload limit.";
  }
  return null;
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (bytes >= 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${bytes} B`;
}

function buildToast(
  tone: ToastMessage["tone"],
  title: string,
  description: string,
): ToastMessage {
  return {
    id: `${tone}-${crypto.randomUUID()}`,
    title,
    description,
    tone,
  };
}

function mapResult(response: IngestResponse): LastResult {
  return {
    source: response.source,
    chunkCount: response.chunk_count,
    storedCount: response.stored_count,
    collectionName: response.collection_name,
    snippets: response.snippets,
  };
}

/** Interactive ingestion UI for file uploads and URL indexing. */
export function IngestionPanel({
  collectionName,
  collections,
  onCollectionSelected,
  onCollectionCreated,
  onCollectionRefreshed,
}: IngestionPanelProps) {
  const inputId = useId();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [urlValue, setUrlValue] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [isUrlSubmitting, setIsUrlSubmitting] = useState(false);
  const [activeMode, setActiveMode] = useState<ActiveMode>("existing");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [lastResult, setLastResult] = useState<LastResult>(null);
  const [inlineError, setInlineError] = useState<string | null>(null);

  const effectiveCollectionName = useMemo(() => {
    if (activeMode === "new") {
      return newCollectionName.trim() || collectionName;
    }
    return collectionName;
  }, [activeMode, collectionName, newCollectionName]);

  const pushToast = useCallback((toast: ToastMessage) => {
    setToasts((current) => [...current, toast]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const syncCollection = useCallback(
    (name: string): string | null => {
      if (activeMode === "new") {
        const created = onCollectionCreated(name);
        if (created) {
          onCollectionRefreshed(created);
          onCollectionSelected(created);
        }
        return created;
      }
      onCollectionRefreshed(name);
      onCollectionSelected(name);
      return name;
    },
    [activeMode, onCollectionCreated, onCollectionRefreshed, onCollectionSelected],
  );

  const handleFileSelection = useCallback((file: File | null) => {
    setSelectedFile(file);
    setInlineError(validateFile(file));
    setLastResult(null);
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLButtonElement>) => {
      event.preventDefault();
      setIsDragging(false);
      const file = event.dataTransfer.files.item(0);
      handleFileSelection(file);
    },
    [handleFileSelection],
  );

  const handleDragState = useCallback((event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setIsDragging(event.type !== "dragleave");
  }, []);

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      handleFileSelection(event.target.files?.item(0) ?? null);
    },
    [handleFileSelection],
  );

  const resetFileState = useCallback(() => {
    setSelectedFile(null);
    setUploadStatus("idle");
    setUploadProgress(0);
    setInlineError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const handleUploadSubmit = useCallback(async () => {
    const collection = effectiveCollectionName.trim() || DEFAULT_COLLECTION;
    const fileError = validateFile(selectedFile);
    if (fileError) {
      setInlineError(fileError);
      setUploadStatus("error");
      pushToast(buildToast("error", "Upload blocked", fileError));
      return;
    }

    setInlineError(null);
    setUploadStatus("uploading");
    setUploadProgress(5);
    setLastResult(null);

    try {
      const response = await ingestFile({
        file: selectedFile as File,
        collectionName: collection,
        onProgress: (progress) => {
          setUploadProgress(progress);
          setUploadStatus(progress >= 95 ? "indexing" : "uploading");
        },
      });
      setUploadProgress(100);
      setUploadStatus("success");
      setLastResult(mapResult(response));
      const syncedCollection = syncCollection(response.collection_name);
      if (activeMode === "new" && syncedCollection) {
        setNewCollectionName("");
        setActiveMode("existing");
      }
      pushToast(
        buildToast(
          "success",
          "Documents indexed",
          `${response.chunk_count} chunks stored in ${response.collection_name}.`,
        ),
      );
    } catch (error) {
      const apiError = toApiError(error);
      setUploadStatus("error");
      setUploadProgress(0);
      setInlineError(apiError.message);
      pushToast(buildToast("error", "Upload failed", apiError.message));
    }
  }, [
    activeMode,
    effectiveCollectionName,
    pushToast,
    selectedFile,
    syncCollection,
  ]);

  const handleUrlSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const nextUrlError = validateUrl(urlValue);
      if (nextUrlError) {
        setUrlError(nextUrlError);
        pushToast(buildToast("error", "Invalid URL", nextUrlError));
        return;
      }

      const collection = effectiveCollectionName.trim() || DEFAULT_COLLECTION;
      setUrlError(null);
      setInlineError(null);
      setIsUrlSubmitting(true);
      setLastResult(null);

      try {
        const response = await ingestUrl({
          url: urlValue.trim(),
          collectionName: collection,
        });
        setLastResult(mapResult(response));
        const syncedCollection = syncCollection(response.collection_name);
        if (activeMode === "new" && syncedCollection) {
          setNewCollectionName("");
          setActiveMode("existing");
        }
        setUrlValue("");
        pushToast(
          buildToast(
            "success",
            "URL indexed",
            `${response.chunk_count} chunks stored in ${response.collection_name}.`,
          ),
        );
      } catch (error) {
        const apiError = toApiError(error);
        setInlineError(apiError.message);
        pushToast(buildToast("error", "URL ingestion failed", apiError.message));
      } finally {
        setIsUrlSubmitting(false);
      }
    },
    [activeMode, effectiveCollectionName, pushToast, syncCollection, urlValue],
  );

  const uploadLabel =
    uploadStatus === "indexing"
      ? "Indexing content"
      : uploadStatus === "uploading"
        ? "Uploading file"
        : uploadStatus === "success"
          ? "Upload complete"
          : uploadStatus === "error"
            ? "Upload failed"
            : "Ready";

  return (
    <>
      <Card className="flex h-full min-h-[540px] flex-col">
        <CardHeader className="border-b border-zinc-800/60">
          <div className="flex items-center justify-between gap-2">
            <div>
              <CardTitle>Ingestion</CardTitle>
              <CardDescription>
                Upload PDF or CSV files, or ingest a public URL into{" "}
                <span className="font-medium text-zinc-200">
                  {effectiveCollectionName}
                </span>
                .
              </CardDescription>
            </div>
            <Badge
              variant="secondary"
              className="border-emerald-500/20 bg-emerald-500/10 text-emerald-200"
            >
              Index
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col gap-4 pt-4">
          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <section className="glass-soft space-y-3 rounded-2xl p-4">
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-zinc-100">
                  Collection target
                </h3>
                <p className="text-sm text-zinc-400">
                  Choose an existing collection or create a new one before indexing.
                </p>
              </div>

              <div className="relative flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant={activeMode === "existing" ? "default" : "outline"}
                  onClick={() => setActiveMode("existing")}
                >
                  Existing collection
                </Button>
                <Button
                  type="button"
                  variant={activeMode === "new" ? "default" : "outline"}
                  onClick={() => setActiveMode("new")}
                >
                  New collection
                </Button>
              </div>

              {activeMode === "existing" ? (
                <div className="space-y-2">
                  <Label htmlFor={`${inputId}-collection`} className="text-zinc-300">
                    Collection
                  </Label>
                  <div className="relative">
                    <select
                      id={`${inputId}-collection`}
                      className="flex h-10 w-full appearance-none rounded-xl border border-zinc-700/70 bg-zinc-950/60 px-3 pr-10 text-sm text-zinc-100 outline-none transition-colors focus-visible:border-violet-500/50 focus-visible:ring-3 focus-visible:ring-violet-500/25"
                      value={collectionName}
                      onChange={(event) => onCollectionSelected(event.target.value)}
                    >
                      {collections.map((collection) => (
                        <option key={collection} value={collection}>
                          {collection}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-zinc-500" />
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <Label
                    htmlFor={`${inputId}-new-collection`}
                    className="text-zinc-300"
                  >
                    New collection name
                  </Label>
                  <Input
                    id={`${inputId}-new-collection`}
                    value={newCollectionName}
                    onChange={(event) => setNewCollectionName(event.target.value)}
                    placeholder="customer_docs"
                    maxLength={63}
                  />
                </div>
              )}
            </section>

            <section className="glass-soft space-y-3 rounded-2xl p-4">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-zinc-100">
                    Processing status
                  </h3>
                  <p className="text-sm text-zinc-400">
                    Live progress while the backend validates and indexes content.
                  </p>
                </div>
                <Badge
                  variant="outline"
                  className={cn(
                    "border-zinc-700 text-zinc-300",
                    uploadStatus === "success" &&
                      "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
                    uploadStatus === "error" &&
                      "border-red-500/40 bg-red-500/10 text-red-200",
                  )}
                >
                  {uploadLabel}
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="h-2 overflow-hidden rounded-full bg-zinc-800/80">
                  <motion.div
                    className={cn(
                      "h-full rounded-full",
                      uploadStatus === "error"
                        ? "bg-red-400"
                        : "accent-gradient",
                    )}
                    initial={false}
                    animate={{
                      width: `${Math.max(
                        uploadProgress,
                        uploadStatus === "success" ? 100 : 0,
                      )}%`,
                    }}
                    transition={{ duration: 0.25 }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-zinc-500">
                  <span>{uploadLabel}</span>
                  <span>{uploadProgress}%</span>
                </div>
              </div>
              {lastResult ? (
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 size-4 text-emerald-400" />
                    <div className="space-y-1">
                      <p className="font-medium text-zinc-100">
                        Latest ingest succeeded
                      </p>
                      <p className="text-zinc-400">
                        {lastResult.storedCount} chunks stored from{" "}
                        {lastResult.source}.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-zinc-700/70 p-3 text-sm text-zinc-500">
                  Start a file or URL ingest to see indexed chunk totals and
                  extracted snippets.
                </div>
              )}
            </section>
          </div>

          <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-2">
            <section className="glass-soft flex flex-col gap-4 rounded-2xl p-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
                  <FileUp className="size-4 text-violet-300" />
                  File upload
                </div>
                <p className="text-sm text-zinc-400">
                  Drag and drop a PDF or CSV file, or browse your device.
                </p>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_TYPES.join(",")}
                className="hidden"
                onChange={handleFileInputChange}
              />

              <motion.button
                type="button"
                onDragEnter={handleDragState}
                onDragOver={handleDragState}
                onDragLeave={handleDragState}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                className={cn(
                  "flex min-h-48 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed px-6 py-8 text-center transition-colors",
                  isDragging
                    ? "border-violet-400/60 bg-violet-500/10 shadow-[0_0_28px_rgba(139,92,246,0.2)]"
                    : "border-zinc-700/70 bg-zinc-950/35 hover:border-emerald-400/40 hover:bg-zinc-900/50",
                )}
              >
                <div className="flex size-12 items-center justify-center rounded-2xl border border-zinc-700/70 bg-zinc-900/70">
                  <UploadCloud className="size-6 text-emerald-300" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-zinc-100">
                    Drop your PDF or CSV here, or click to browse
                  </p>
                  <p className="text-xs text-zinc-500">Maximum file size: 25 MB</p>
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  <Badge variant="outline" className="border-zinc-700 text-zinc-300">
                    PDF
                  </Badge>
                  <Badge variant="outline" className="border-zinc-700 text-zinc-300">
                    CSV
                  </Badge>
                </div>
              </motion.button>

              <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/45 p-3 text-sm">
                {selectedFile ? (
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-zinc-100">
                        {selectedFile.name}
                      </p>
                      <p className="text-xs text-zinc-500">
                        {formatFileSize(selectedFile.size)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button type="button" variant="ghost" onClick={resetFileState}>
                        Reset
                      </Button>
                      <Button
                        type="button"
                        onClick={() => void handleUploadSubmit()}
                        disabled={
                          uploadStatus === "uploading" ||
                          uploadStatus === "indexing"
                        }
                      >
                        {uploadStatus === "uploading" ||
                        uploadStatus === "indexing" ? (
                          <>
                            <LoaderCircle className="size-4 animate-spin" />
                            Processing
                          </>
                        ) : (
                          <>
                            <UploadCloud className="size-4" />
                            Upload file
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-zinc-500">
                    <Table className="size-4" />
                    No file selected yet.
                  </div>
                )}
              </div>
            </section>

            <section className="glass-soft flex min-h-0 flex-col gap-4 rounded-2xl p-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
                  <Globe className="size-4 text-emerald-300" />
                  URL ingestion
                </div>
                <p className="text-sm text-zinc-400">
                  Submit a public page URL for extraction, chunking, and indexing.
                </p>
              </div>

              <form className="flex flex-col gap-3" onSubmit={handleUrlSubmit}>
                <div className="space-y-2">
                  <Label htmlFor={`${inputId}-url`} className="text-zinc-300">
                    Public URL
                  </Label>
                  <Input
                    id={`${inputId}-url`}
                    type="url"
                    value={urlValue}
                    onChange={(event) => {
                      setUrlValue(event.target.value);
                      if (urlError) {
                        setUrlError(null);
                      }
                    }}
                    placeholder="https://example.com/docs"
                    aria-invalid={Boolean(urlError)}
                    className="h-11"
                  />
                  {urlError ? (
                    <p className="text-xs text-red-300">{urlError}</p>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="submit" disabled={isUrlSubmitting}>
                    {isUrlSubmitting ? (
                      <>
                        <LoaderCircle className="size-4 animate-spin" />
                        Indexing URL
                      </>
                    ) : (
                      <>
                        <Globe className="size-4" />
                        Ingest URL
                      </>
                    )}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setUrlValue("");
                      setUrlError(null);
                    }}
                  >
                    <RefreshCcw className="size-4" />
                    Clear
                  </Button>
                </div>
              </form>

              <Separator className="bg-zinc-800/80" />

              <div className="flex min-h-0 flex-1 flex-col gap-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-zinc-100">
                    Preview snippets
                  </p>
                  {lastResult ? (
                    <Badge
                      variant="outline"
                      className="border-zinc-700 text-zinc-300"
                    >
                      {lastResult.chunkCount} chunks
                    </Badge>
                  ) : null}
                </div>
                <ScrollArea className="min-h-0 flex-1 rounded-xl border border-zinc-800/70 bg-zinc-950/40">
                  <div className="space-y-3 p-4">
                    {lastResult?.snippets.length ? (
                      lastResult.snippets.map((snippet) => (
                        <div
                          key={snippet}
                          className="rounded-lg border border-zinc-800/80 bg-zinc-900/50 p-3 text-sm text-zinc-400"
                        >
                          {snippet}
                        </div>
                      ))
                    ) : (
                      <div className="flex min-h-40 flex-col items-center justify-center gap-3 text-center text-sm text-zinc-500">
                        <XCircle className="size-5" />
                        Run an ingest to preview extracted chunk snippets.
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>
            </section>
          </div>

          {inlineError ? (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {inlineError}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
