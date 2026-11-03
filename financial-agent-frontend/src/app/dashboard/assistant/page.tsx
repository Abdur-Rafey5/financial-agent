"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Bot, MessageSquare, Send, Sparkles, Trash2, User } from "lucide-react";
import { assistantApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AssistantMessage, ChatResponse, ConversationSummary } from "@/lib/types";
import {
  Button,
  ErrorBanner,
  LoadingBlock,
  Modal,
  Textarea,
  Badge,
} from "@/components/ui";
import { PageHeader } from "@/components/app-shell";
import { formatDateTime } from "@/lib/format";

const SUGGESTIONS = [
  "How much did I spend this month and on what?",
  "How is my savings rate looking?",
  "Give me a summary of my budgets.",
  "What should I focus on financially right now?",
];

export default function AssistantPage() {
  const { profile } = useAuth();

  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [aiGenerated, setAiGenerated] = useState<boolean | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    try {
      setConversations(await assistantApi.conversations(30));
    } catch {
      /* history is optional */
    }
  }, []);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const send = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || sending) return;
    setInput("");
    setError(null);
    setSending(true);
    // Optimistically show the user's message
    setMessages((prev) => [
      ...prev,
      {
        id: `local-${Date.now()}`,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
      },
    ]);
    try {
      const res: ChatResponse = await assistantApi.chat({
        message,
        conversation_id: conversationId,
      });
      setConversationId(res.conversation_id);
      setAiGenerated(res.ai_generated);
      setMessages((prev) => [...prev, res.message]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The assistant could not reply.");
    } finally {
      setSending(false);
      void loadConversations();
    }
  };

  const openConversation = async (id: string) => {
    setHistoryOpen(false);
    setLoadingHistory(true);
    setError(null);
    try {
      const detail = await assistantApi.conversation(id);
      setConversationId(detail.id);
      setMessages(detail.messages);
      setAiGenerated(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the conversation.");
    } finally {
      setLoadingHistory(false);
    }
  };

  const newConversation = () => {
    setConversationId(null);
    setMessages([]);
    setAiGenerated(null);
    setError(null);
  };

  const deleteConversation = async (id: string) => {
    try {
      await assistantApi.deleteConversation(id);
      if (id === conversationId) newConversation();
      await loadConversations();
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="flex flex-col">
      <PageHeader
        icon={<Bot className="h-6 w-6" />}
        title="AI Assistant"
        description="Grounded in your real numbers — it explains what your data shows, never invents figures."
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setHistoryOpen(true)}>
              <MessageSquare className="h-4 w-4" /> History
            </Button>
            <Button variant="ghost" onClick={newConversation}>
              New chat
            </Button>
          </div>
        }
      />

      {/* Banner note about grounding */}
      {aiGenerated === false && (
        <div className="mb-4">
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">
            No AI provider is configured, so this reply is a factual summary generated from your
            financial snapshot by the backend — no invented numbers.
          </div>
        </div>
      )}

      <div className="flex min-h-[55vh] flex-1 flex-col rounded-2xl border border-slate-800/70 bg-slate-900/40">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-5">
          {loadingHistory ? (
            <LoadingBlock label="Loading conversation…" />
          ) : messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 py-10 text-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-500 to-emerald-400 shadow-lg shadow-indigo-500/25">
                <Sparkles className="h-7 w-7 text-white" />
              </span>
              <div>
                <h3 className="text-base font-bold text-white">
                  Hi {profile?.full_name?.split(" ")[0] ?? "there"} — ask me anything about your money
                </h3>
                <p className="mx-auto mt-1 max-w-md text-xs text-slate-500">
                  Every answer is based on your actual recorded income, expenses, budgets and goals.
                  The assistant can explain but never fabricates.
                </p>
              </div>
              <div className="mt-2 grid w-full max-w-md grid-cols-1 gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void send(suggestion)}
                    className="rounded-xl border border-slate-700/70 px-4 py-2.5 text-left text-xs text-slate-300 transition-colors hover:border-indigo-500/50 hover:bg-slate-800/60 hover:text-white"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => {
              const isUser = message.role === "user";
              return (
                <div
                  key={message.id}
                  className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}
                >
                  <span
                    className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${
                      isUser
                        ? "bg-slate-700 text-slate-200"
                        : "bg-gradient-to-tr from-indigo-500 to-emerald-400 text-white"
                    }`}
                  >
                    {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </span>
                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      isUser
                        ? "bg-indigo-600/80 text-white"
                        : "border border-slate-700/60 bg-slate-800/60 text-slate-200"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    <p
                      className={`mt-1.5 text-[10px] ${
                        isUser ? "text-indigo-200" : "text-slate-500"
                      }`}
                    >
                      {formatDateTime(message.created_at)}
                    </p>
                  </div>
                </div>
              );
            })
          )}
          {sending && (
            <div className="flex gap-3">
              <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-tr from-indigo-500 to-emerald-400">
                <Bot className="h-4 w-4 text-white" />
              </span>
              <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 px-4 py-3">
                <span className="flex gap-1.5">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:120ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:240ms]" />
                </span>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="px-5 pb-3">
            <ErrorBanner message={error} />
          </div>
        )}

        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            void send();
          }}
          className="flex items-end gap-2 border-t border-slate-800/70 p-4"
        >
          <Textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            placeholder="Ask about your spending, savings, budgets or goals…"
            className="max-h-32 flex-1"
            maxLength={4000}
          />
          <Button type="submit" loading={sending} disabled={!input.trim()}>
            <Send className="h-4 w-4" /> Send
          </Button>
        </form>
      </div>

      {/* History modal */}
      <Modal open={historyOpen} onClose={() => setHistoryOpen(false)} title="Conversation history">
        {conversations.length ? (
          <div className="max-h-[50vh] space-y-2 overflow-y-auto">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-slate-800/70 px-4 py-3"
              >
                <button
                  type="button"
                  onClick={() => void openConversation(conversation.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <p className="truncate text-sm font-medium text-white">
                    {conversation.title || "Untitled chat"}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-slate-500">
                    {conversation.last_message || "—"}
                  </p>
                  <Badge tone="slate" className="mt-1.5">
                    {conversation.message_count} messages
                  </Badge>
                </button>
                <button
                  type="button"
                  onClick={() => void deleteConversation(conversation.id)}
                  className="flex-shrink-0 rounded-lg p-2 text-slate-500 hover:bg-red-500/10 hover:text-red-300"
                  aria-label="Delete conversation"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-slate-500">No conversations yet.</p>
        )}
      </Modal>
    </div>
  );
}
