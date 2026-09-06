"use client";

import { Bot, UserRound } from "lucide-react";

import { CitationList } from "@/components/chat/citation-list";
import type { ChatCitation } from "@/lib/api";
import { cn } from "@/lib/utils";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  citations?: ChatCitation[];
  createdAt: string;
  isError?: boolean;
};

type MessageBubbleProps = {
  message: ChatMessage;
};

/** Single chat turn bubble for user or assistant messages. */
export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      <div
        className={cn(
          "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground",
        )}
      >
        {isUser ? <UserRound className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div
        className={cn(
          "max-w-[min(100%,36rem)] rounded-2xl px-4 py-3 text-sm shadow-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : message.isError
              ? "border border-destructive/30 bg-destructive/5 text-destructive"
              : "border border-border bg-background text-foreground",
        )}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        {!isUser && message.citations?.length ? (
          <CitationList citations={message.citations} />
        ) : null}
      </div>
    </div>
  );
}

/** Animated typing indicator shown while the assistant is generating. */
export function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Bot className="size-4" />
      </div>
      <div className="rounded-2xl border border-border bg-background px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1.5" aria-label="Assistant is thinking">
          <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.2s]" />
          <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.1s]" />
          <span className="size-2 animate-bounce rounded-full bg-muted-foreground" />
        </div>
      </div>
    </div>
  );
}
