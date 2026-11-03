"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Lightbulb, Sparkles, Trash2 } from "lucide-react";
import { recommendationsApi } from "@/lib/api";
import type { GenerateResult, Recommendation, RecommendationList } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  LoadingBlock,
  StatCard,
  type Tone,
} from "@/components/ui";
import { PageHeader } from "@/components/app-shell";
import { formatDate } from "@/lib/format";

const PRIORITY_TONES: Record<string, Tone> = {
  high: "red",
  medium: "amber",
  low: "sky",
};

const TYPE_LABELS: Record<string, string> = {
  budget_alert: "Budget",
  savings: "Savings",
  spending: "Spending",
  goal: "Goal",
  business: "Business",
  general: "General",
};

export default function RecommendationsPage() {
  const [list, setList] = useState<RecommendationList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateInfo, setGenerateInfo] = useState<string | null>(null);

  const [unreadOnly, setUnreadOnly] = useState(false);

  const load = useCallback(async (unreadOnly: boolean) => {
    setLoading(true);
    setError(null);
    try {
      setList(await recommendationsApi.list({ unread_only: unreadOnly || undefined }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load insights.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(unreadOnly);
  }, [load, unreadOnly]);

  const generate = async () => {
    setGenerating(true);
    setGenerateInfo(null);
    try {
      const result: GenerateResult = await recommendationsApi.generate();
      setGenerateInfo(
        result.created
          ? `${result.created} new insight${result.created === 1 ? "" : "s"} generated from your latest data.`
          : "No new insights right now — you're all caught up."
      );
      await load(unreadOnly);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate insights.");
    } finally {
      setGenerating(false);
    }
  };

  const markRead = async (id: string) => {
    try {
      await recommendationsApi.markRead(id);
      await load(unreadOnly);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark as read.");
    }
  };

  const dismiss = async (id: string) => {
    try {
      await recommendationsApi.dismiss(id);
      await load(unreadOnly);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dismiss the insight.");
    }
  };

  const readAll = async () => {
    try {
      await recommendationsApi.readAll();
      await load(unreadOnly);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark all as read.");
    }
  };

  const items: Recommendation[] = list?.items ?? [];

  return (
    <div>
      <PageHeader
        icon={<Lightbulb className="h-6 w-6" />}
        title="Insights"
        description="Deterministic recommendations computed from your records — with transparent reasoning."
        action={
          <div className="flex gap-2">
            <Button onClick={() => void generate()} loading={generating}>
              <Sparkles className="h-4 w-4" /> Generate
            </Button>
            {(list?.unread_count ?? 0) > 0 && (
              <Button variant="secondary" onClick={() => void readAll()}>
                <Check className="h-4 w-4" /> Mark all read
              </Button>
            )}
          </div>
        }
      />

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} onRetry={() => void load(unreadOnly)} />
        </div>
      )}

      {generateInfo && (
        <div className="mb-5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          {generateInfo}
        </div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Total Insights" value={list?.total ?? 0} tone="indigo" />
        <StatCard
          label="Unread"
          value={list?.unread_count ?? 0}
          sub={unreadOnly ? "Showing unread only" : undefined}
          tone="amber"
        />
        <button type="button" onClick={() => setUnreadOnly(!unreadOnly)} className="text-left">
          <StatCard
            label="Filter"
            value={unreadOnly ? "Unread only" : "All insights"}
            sub="Tap to toggle"
            tone="sky"
          />
        </button>
      </div>

      {loading ? (
        <LoadingBlock label="Loading insights…" />
      ) : items.length ? (
        <div className="space-y-4">
          {items.map((item) => (
            <Card key={item.id} className={item.is_read ? "opacity-70" : ""}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <Badge tone={PRIORITY_TONES[item.priority] ?? "slate"}>{item.priority}</Badge>
                    <Badge tone="violet">{TYPE_LABELS[item.type] || item.type.replace(/_/g, " ")}</Badge>
                    <span className="text-[11px] text-slate-500">{formatDate(item.created_at)}</span>
                    {!item.is_read && <Badge tone="indigo">new</Badge>}
                  </div>
                  <h3 className="text-base font-bold text-white">{item.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-300">{item.content}</p>
                  {item.reasoning && (
                    <div className="mt-3 rounded-xl border border-slate-800/70 bg-slate-900/50 px-4 py-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Why this matters
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-400">{item.reasoning}</p>
                    </div>
                  )}
                </div>
                <div className="flex flex-shrink-0 flex-col gap-1.5">
                  {!item.is_read && (
                    <button
                      type="button"
                      onClick={() => void markRead(item.id)}
                      className="rounded-lg p-2 text-slate-500 hover:bg-emerald-500/10 hover:text-emerald-300"
                      aria-label="Mark as read"
                      title="Mark as read"
                    >
                      <Check className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void dismiss(item.id)}
                    className="rounded-lg p-2 text-slate-500 hover:bg-red-500/10 hover:text-red-300"
                    aria-label="Dismiss"
                    title="Dismiss"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title={unreadOnly ? "No unread insights" : "No insights yet"}
            description="Insights are derived from your transactions, budgets and goals — never invented. Generate to check for the first time."
            action={
              <Button size="sm" onClick={() => void generate()} loading={generating}>
                <Sparkles className="h-4 w-4" /> Generate insights
              </Button>
            }
          />
        </Card>
      )}
    </div>
  );
}
