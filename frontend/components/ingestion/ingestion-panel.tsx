"use client";

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
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <div>
              <CardTitle>Ingestion</CardTitle>
              <CardDescription>
                Upload PDF or CSV files, or ingest a public URL into{" "}
                <span className="font-medium text-foreground">{effectiveCollectionName}</span>.
              </CardDescription>
            </div>
            <Badge variant="secondary">Phase 2</Badge>
          </div>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col gap-4">
          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <section className="space-y-3 rounded-xl border border-border p-4">
              <div className="space-y-1">
                <h3 className="text-sm font-semibold">Collection target</h3>
                <p className="text-sm text-muted-foreground">
                  Choose an existing collection or create a new one before indexing.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
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
                  <Label htmlFor={`${inputId}-collection`}>Collection</Label>
                  <div className="relative">
                    <select
                      id={`${inputId}-collection`}
                      className="flex h-10 w-full appearance-none rounded-lg border border-input bg-background px-3 pr-10 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                      value={collectionName}
                      onChange={(event) => onCollectionSelected(event.target.value)}
                    >
                      {collections.map((collection) => (
                        <option key={collection} value={collection}>
                          {collection}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground" />
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <Label htmlFor={`${inputId}-new-collection`}>New collection name</Label>
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

            <section className="space-y-3 rounded-xl border border-border p-4">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold">Processing status</h3>
                  <p className="text-sm text-muted-foreground">Live progress while the backend validates and indexes content.</p>
                </div>
                <Badge
                  variant={
                    uploadStatus === "success"
                      ? "secondary"
                      : uploadStatus === "error"
                        ? "destructive"
                        : "outline"
                  }
                >
                  {uploadLabel}
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      uploadStatus === "error" ? "bg-destructive" : "bg-primary",
                    )}
                    style={{ width: `${Math.max(uploadProgress, uploadStatus === "success" ? 100 : 0)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{uploadLabel}</span>
                  <span>{uploadProgress}%</span>
                </div>
              </div>
              {lastResult ? (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3 text-sm dark:border-emerald-900 dark:bg-emerald-950/30">
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 size-4 text-emerald-600" />
                    <div className="space-y-1">
                      <p className="font-medium text-foreground">Latest ingest succeeded</p>
                      <p className="text-muted-foreground">
                        {lastResult.storedCount} chunks stored from {lastResult.source}.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-border p-3 text-sm text-muted-foreground">
                  Start a file or URL ingest to see indexed chunk totals and extracted snippets.
                </div>
              )}
            </section>
          </div>

          <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-2">
            <section className="flex flex-col gap-4 rounded-xl border border-border p-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <FileUp className="size-4" />
                  File upload
                </div>
                <p className="text-sm text-muted-foreground">
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

              <button
                type="button"
                onDragEnter={handleDragState}
                onDragOver={handleDragState}
                onDragLeave={handleDragState}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "flex min-h-48 flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-8 text-center transition-colors",
                  isDragging
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/40",
                )}
              >
                <UploadCloud className="size-8 text-muted-foreground" />
                <div className="space-y-1">
                  <p className="text-sm font-medium">
                    Drop your PDF or CSV here, or click to browse
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Maximum file size: 25 MB
                  </p>
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  <Badge variant="outline">PDF</Badge>
                  <Badge variant="outline">CSV</Badge>
                </div>
              </button>

              <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm">
                {selectedFile ? (
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{selectedFile.name}</p>
                      <p className="text-xs text-muted-foreground">
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
                        disabled={uploadStatus === "uploading" || uploadStatus === "indexing"}
                      >
                        {uploadStatus === "uploading" || uploadStatus === "indexing" ? (
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
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Table className="size-4" />
                    No file selected yet.
                  </div>
                )}
              </div>
            </section>

            <section className="flex min-h-0 flex-col gap-4 rounded-xl border border-border p-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Globe className="size-4" />
                  URL ingestion
                </div>
                <p className="text-sm text-muted-foreground">
                  Submit a public page URL for extraction, chunking, and indexing.
                </p>
              </div>

              <form className="flex flex-col gap-3" onSubmit={handleUrlSubmit}>
                <div className="space-y-2">
                  <Label htmlFor={`${inputId}-url`}>Public URL</Label>
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
                  />
                  {urlError ? (
                    <p className="text-xs text-destructive">{urlError}</p>
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

              <Separator />

              <div className="flex min-h-0 flex-1 flex-col gap-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">Preview snippets</p>
                  {lastResult ? (
                    <Badge variant="outline">{lastResult.chunkCount} chunks</Badge>
                  ) : null}
                </div>
                <ScrollArea className="min-h-0 flex-1 rounded-xl border border-border bg-muted/20">
                  <div className="space-y-3 p-4">
                    {lastResult?.snippets.length ? (
                      lastResult.snippets.map((snippet) => (
                        <div key={snippet} className="rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">
                          {snippet}
                        </div>
                      ))
                    ) : (
                      <div className="flex min-h-40 flex-col items-center justify-center gap-3 text-center text-sm text-muted-foreground">
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
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {inlineError}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
