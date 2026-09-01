"use client";

import { FileUp, Globe, Table } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type IngestionPanelProps = {
  collectionName: string;
};

/** Phase 1 placeholder for PDF, CSV, and URL ingestion workflows. */
export function IngestionPanel({ collectionName }: IngestionPanelProps) {
  return (
    <Card className="flex h-full min-h-[420px] flex-col">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle>Ingestion</CardTitle>
            <CardDescription>
              Upload documents or fetch URLs into{" "}
              <span className="font-medium text-foreground">{collectionName}</span>.
            </CardDescription>
          </div>
          <Badge variant="secondary">Phase 1 shell</Badge>
        </div>
      </CardHeader>
      <CardContent className="grid flex-1 gap-3 sm:grid-cols-3">
        <div className="flex flex-col items-start gap-2 rounded-xl border border-dashed border-border p-4">
          <FileUp className="size-5 text-muted-foreground" />
          <p className="text-sm font-medium">PDF upload</p>
          <p className="text-xs text-muted-foreground">
            Connects to <code className="text-foreground">POST /api/v1/ingest/file</code>
          </p>
        </div>
        <div className="flex flex-col items-start gap-2 rounded-xl border border-dashed border-border p-4">
          <Table className="size-5 text-muted-foreground" />
          <p className="text-sm font-medium">CSV upload</p>
          <p className="text-xs text-muted-foreground">
            Row-level metadata preserved during chunking.
          </p>
        </div>
        <div className="flex flex-col items-start gap-2 rounded-xl border border-dashed border-border p-4">
          <Globe className="size-5 text-muted-foreground" />
          <p className="text-sm font-medium">URL ingest</p>
          <p className="text-xs text-muted-foreground">
            Connects to <code className="text-foreground">POST /api/v1/ingest/url</code>
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
