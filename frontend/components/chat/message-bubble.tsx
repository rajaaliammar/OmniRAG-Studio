"use client";

import { motion } from "motion/react";
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
  index?: number;
};

/** Gemini-style dark message bubble with staggered cinematic entry. */
export function MessageBubble({ message, index = 0 }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 14, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.32,
        delay: Math.min(index * 0.04, 0.24),
        ease: [0.22, 1, 0.36, 1],
      }}
      className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
    >
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: Math.min(index * 0.04, 0.24) + 0.05, duration: 0.25 }}
        className={cn(
          "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border transition-all duration-300",
          isUser
            ? "accent-gradient border-transparent text-white shadow-[0_0_18px_rgba(6,182,212,0.35)]"
            : "border-slate-700/80 bg-slate-900/80 text-emerald-300",
        )}
      >
        {isUser ? <UserRound className="size-4" /> : <Bot className="size-4" />}
      </motion.div>
      <div
        className={cn(
          "max-w-[min(100%,36rem)] rounded-2xl px-4 py-3 text-sm shadow-lg transition-all duration-300",
          isUser
            ? "accent-gradient text-slate-950 shadow-[0_8px_28px_rgba(6,182,212,0.22)] hover:scale-[1.02] hover:shadow-[0_10px_32px_rgba(16,185,129,0.28)]"
            : message.isError
              ? "border border-red-500/30 bg-red-500/10 text-red-200"
              : "glass-soft text-slate-100 hover:scale-[1.02] hover:border-cyan-400/35 hover:shadow-[0_0_24px_rgba(6,182,212,0.14)]",
        )}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        {!isUser && message.citations?.length ? (
          <CitationList citations={message.citations} />
        ) : null}
      </div>
    </motion.div>
  );
}

/** Animated typing indicator shown while the assistant is generating. */
export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-3"
    >
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border border-slate-700/80 bg-slate-900/80 text-emerald-300">
        <Bot className="size-4" />
      </div>
      <div className="glass-soft rounded-2xl px-4 py-3 shadow-lg">
        <div className="flex items-center gap-1.5" aria-label="Assistant is thinking">
          <span className="size-2 animate-bounce rounded-full bg-cyan-400 [animation-delay:-0.2s]" />
          <span className="size-2 animate-bounce rounded-full bg-emerald-400 [animation-delay:-0.1s]" />
          <span className="size-2 animate-bounce rounded-full bg-blue-400" />
        </div>
      </div>
    </motion.div>
  );
}
