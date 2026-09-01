"use client";

import { Bot, MessageSquareQuote } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

type ChatPanelProps = {
  collectionName: string;
};

/** Phase 1 placeholder for grounded RAG chat against a collection. */
export function ChatPanel({ collectionName }: ChatPanelProps) {
  return (
    <Card className="flex h-full min-h-[420px] flex-col">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle>Chat</CardTitle>
            <CardDescription>
              Ask questions grounded in{" "}
              <span className="font-medium text-foreground">{collectionName}</span>{" "}
              with source citations.
            </CardDescription>
          </div>
          <Badge variant="secondary">Phase 1 shell</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-4">
        <ScrollArea className="flex-1 rounded-xl border border-border bg-muted/30 p-4">
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-muted-foreground">
            <MessageSquareQuote className="size-8" />
            <p className="max-w-sm text-sm">
              Chat history and query submission will connect to{" "}
              <code className="text-foreground">POST /api/v1/chat/query</code> in
              the next phase.
            </p>
          </div>
        </ScrollArea>
        <div className="flex items-center gap-2 rounded-xl border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
          <Bot className="size-4 shrink-0" />
          Session memory and citation rendering arrive in Phase 2.
        </div>
      </CardContent>
    </Card>
  );
}
