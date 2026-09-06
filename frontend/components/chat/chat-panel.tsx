"use client";

import { AnimatePresence, motion } from "motion/react";
import {
  Eraser,
  LoaderCircle,
  MessageSquareQuote,
  SendHorizontal,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import {
  MessageBubble,
  TypingIndicator,
  type ChatMessage,
} from "@/components/chat/message-bubble";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ToastStack, type ToastMessage } from "@/components/ui/toast-stack";
import {
  chatQuery,
  clearChatSession,
  toApiError,
} from "@/lib/api";

type ChatPanelProps = {
  collectionName: string;
};

function createMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildToast(
  tone: ToastMessage["tone"],
  title: string,
  description: string,
): ToastMessage {
  return {
    id: `${tone}-${createMessageId()}`,
    title,
    description,
    tone,
  };
}

/** Interactive RAG chat panel with session memory and citation display. */
export function ChatPanel({ collectionName }: ChatPanelProps) {
  const inputId = useId();
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isThinking, setIsThinking] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isThinking]);

  const pushToast = useCallback((toast: ToastMessage) => {
    setToasts((current) => [...current, toast]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const handleClearSession = useCallback(async () => {
    if (!sessionId && messages.length === 0) {
      return;
    }
    try {
      if (sessionId) {
        await clearChatSession(sessionId);
      }
      setMessages([]);
      setSessionId(null);
      setInlineError(null);
      setInput("");
      pushToast(
        buildToast(
          "success",
          "Session cleared",
          "Conversation memory was reset for this chat.",
        ),
      );
    } catch (error) {
      const apiError = toApiError(error);
      setInlineError(apiError.message);
      pushToast(buildToast("error", "Clear failed", apiError.message));
    }
  }, [messages.length, pushToast, sessionId]);

  const submitQuery = useCallback(async () => {
    const query = input.trim();
    if (!query) {
      setInlineError("Enter a question before sending.");
      pushToast(
        buildToast(
          "error",
          "Empty query",
          "Enter a non-empty question to ask the assistant.",
        ),
      );
      return;
    }

    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: query,
      createdAt: new Date().toISOString(),
    };

    setMessages((current) => [...current, userMessage]);
    setInput("");
    setInlineError(null);
    setIsThinking(true);

    try {
      const response = await chatQuery({
        query,
        collectionName,
        sessionId,
      });
      setSessionId(response.session_id);
      const assistantMessage: ChatMessage = {
        id: createMessageId(),
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        createdAt: new Date().toISOString(),
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch (error) {
      const apiError = toApiError(error);
      setInlineError(apiError.message);
      setMessages((current) => [
        ...current,
        {
          id: createMessageId(),
          role: "assistant",
          content: apiError.message,
          createdAt: new Date().toISOString(),
          isError: true,
        },
      ]);
      pushToast(buildToast("error", "Chat failed", apiError.message));
    } finally {
      setIsThinking(false);
    }
  }, [collectionName, input, pushToast, sessionId]);

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (isThinking) {
        return;
      }
      void submitQuery();
    },
    [isThinking, submitQuery],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (!isThinking) {
          void submitQuery();
        }
      }
    },
    [isThinking, submitQuery],
  );

  return (
    <>
      <Card className="flex h-full min-h-[540px] flex-col">
        <CardHeader className="border-b border-zinc-800/60">
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>Chat</CardTitle>
              <CardDescription>
                Ask grounded questions against{" "}
                <span className="font-medium text-zinc-200">
                  {collectionName}
                </span>
                .
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Badge
                variant="secondary"
                className="border-violet-500/20 bg-violet-500/10 text-violet-200"
              >
                Live
              </Badge>
              {sessionId ? (
                <Badge
                  variant="outline"
                  className="max-w-[10rem] truncate border-zinc-700 text-zinc-300"
                >
                  {sessionId.slice(0, 8)}…
                </Badge>
              ) : (
                <Badge variant="outline" className="border-zinc-700 text-zinc-400">
                  New session
                </Badge>
              )}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void handleClearSession()}
                disabled={isThinking || (!sessionId && messages.length === 0)}
              >
                <Eraser className="size-3.5" />
                Clear
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="flex min-h-0 flex-1 flex-col gap-4 pt-4">
          <ScrollArea className="min-h-0 flex-1 rounded-2xl border border-zinc-800/70 bg-zinc-950/40">
            <div className="space-y-4 p-4">
              <AnimatePresence mode="popLayout">
                {messages.length === 0 && !isThinking ? (
                  <motion.div
                    key="empty"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex min-h-[18rem] flex-col items-center justify-center gap-3 px-4 text-center text-zinc-400"
                  >
                    <div className="flex size-12 items-center justify-center rounded-2xl border border-zinc-700/70 bg-zinc-900/60">
                      <MessageSquareQuote className="size-6 text-violet-300" />
                    </div>
                    <div className="max-w-sm space-y-1">
                      <p className="text-sm font-medium text-zinc-100">
                        Start a grounded conversation
                      </p>
                      <p className="text-sm">
                        Ask about content in{" "}
                        <span className="font-medium text-zinc-200">
                          {collectionName}
                        </span>
                        . Source chips appear when retrieval finds matches.
                      </p>
                    </div>
                  </motion.div>
                ) : (
                  messages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
                  ))
                )}
              </AnimatePresence>
              {isThinking ? <TypingIndicator /> : null}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          {inlineError ? (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {inlineError}
            </div>
          ) : null}

          <form className="space-y-2" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor={inputId}>
              Chat message
            </label>
            <div className="flex items-end gap-2 rounded-2xl border border-zinc-700/70 bg-zinc-950/55 p-2 shadow-[0_0_0_1px_rgba(139,92,246,0.08)_inset] backdrop-blur-sm transition-colors focus-within:border-violet-500/40">
              <textarea
                id={inputId}
                value={input}
                onChange={(event) => {
                  setInput(event.target.value);
                  if (inlineError) {
                    setInlineError(null);
                  }
                }}
                onKeyDown={handleKeyDown}
                rows={2}
                placeholder="Ask a question about the selected collection…"
                className="min-h-[2.75rem] max-h-32 w-full resize-none bg-transparent px-2 py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
                disabled={isThinking}
              />
              <Button
                type="submit"
                size="icon"
                disabled={isThinking || !input.trim()}
                aria-label="Send message"
              >
                {isThinking ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <SendHorizontal className="size-4" />
                )}
              </Button>
            </div>
            <p className="text-xs text-zinc-500">
              Press Enter to send · Shift+Enter for a new line
            </p>
          </form>
        </CardContent>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
