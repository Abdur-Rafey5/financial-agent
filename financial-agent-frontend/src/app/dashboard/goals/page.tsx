"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CalendarDays, PiggyBank, Plus, Target, Trash2 } from "lucide-react";
import { goalsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Goal } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  LoadingBlock,
  Modal,
  ProgressBar,
  Textarea,
} from "@/components/ui";
import { PageHeader } from "@/components/app-shell";
import { addDaysISO, currencySymbol, formatDate, formatMoney, formatPercent } from "@/lib/format";

const STATUS_TONES: Record<string, "emerald" | "indigo" | "slate" | "red"> = {
  completed: "emerald",
  active: "indigo",
  cancelled: "slate",
};

export default function GoalsPage() {
  const { profile } = useAuth();
  const currency = profile?.currency ?? "PKR";

  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setGoals(await goalsApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load goals.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // ── Create / edit modal ─────────────────────────────────────────
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Goal | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [targetAmount, setTargetAmount] = useState("");
  const [targetDate, setTargetDate] = useState("");

  // ── Contribution modal ──────────────────────────────────────────
  const [contribGoal, setContribGoal] = useState<Goal | null>(null);
  const [contribAmount, setContribAmount] = useState("");
  const [contribDate, setContribDate] = useState(new Date().toISOString().slice(0, 10));
  const [contribNotes, setContribNotes] = useState("");
  const [contribSaving, setContribSaving] = useState(false);
  const [contribError, setContribError] = useState<string | null>(null);

  const openCreate = () => {
    setEditing(null);
    setTitle("");
    setDescription("");
    setTargetAmount("");
    setTargetDate(addDaysISO(new Date().toISOString().slice(0, 10), 90));
    setFormError(null);
    setOpen(true);
  };

  const openEdit = (goal: Goal) => {
    setEditing(goal);
    setTitle(goal.title);
    setDescription(goal.description ?? "");
    setTargetAmount(String(goal.target_amount));
    setTargetDate(goal.target_date ?? "");
    setFormError(null);
    setOpen(true);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const amount = parseFloat(targetAmount);
    if (!amount || amount <= 0) {
      setFormError("Enter a valid target amount.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        title: title.trim(),
        description: description.trim() || undefined,
        target_amount: amount,
        target_date: targetDate || undefined,
      };
      if (editing) {
        await goalsApi.update(editing.id, payload);
      } else {
        await goalsApi.create({ ...payload, currency });
      }
      setOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to save the goal.");
    } finally {
      setSaving(false);
    }
  };

  const submitContribution = async (e: FormEvent) => {
    e.preventDefault();
    if (!contribGoal) return;
    setContribError(null);
    const amount = parseFloat(contribAmount);
    if (!amount || amount <= 0) {
      setContribError("Enter a valid contribution amount.");
      return;
    }
    setContribSaving(true);
    try {
      await goalsApi.contribute(contribGoal.id, {
        amount,
        date: contribDate,
        notes: contribNotes || undefined,
      });
      setContribGoal(null);
      setContribAmount("");
      setContribNotes("");
      await load();
    } catch (err) {
      setContribError(err instanceof Error ? err.message : "Failed to record the contribution.");
    } finally {
      setContribSaving(false);
    }
  };

  const remove = async (goal: Goal) => {
    try {
      await goalsApi.delete(goal.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete the goal.");
    }
  };

  const setStatus = async (goal: Goal, status: string) => {
    try {
      await goalsApi.update(goal.id, { status });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update the goal.");
    }
  };

  const removeContribution = async (goal: Goal, contributionId: string) => {
    try {
      await goalsApi.deleteContribution(goal.id, contributionId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete the contribution.");
    }
  };

  const activeGoal = goals.find((g) => g.id === contribGoal?.id);

  return (
    <div>
      <PageHeader
        icon={<PiggyBank className="h-6 w-6" />}
        title="Goals"
        description="Set savings targets and track them with a full contribution ledger."
        action={
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" /> New goal
          </Button>
        }
      />

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} onRetry={() => void load()} />
        </div>
      )}

      {loading ? (
        <LoadingBlock label="Loading goals…" />
      ) : goals.length ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {goals.map((goal) => {
            const daysLeft = goal.target_date
              ? Math.ceil(
                  (new Date(`${goal.target_date}T00:00:00`).getTime() - Date.now()) / 86400000
                )
              : null;
            return (
              <Card key={goal.id} hover>
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-bold text-white">{goal.title}</h3>
                      <Badge tone={STATUS_TONES[goal.status] ?? "slate"}>{goal.status}</Badge>
                    </div>
                    {goal.description && (
                      <p className="mt-1 line-clamp-2 text-xs text-slate-500">{goal.description}</p>
                    )}
                  </div>
                  <div className="flex flex-shrink-0 gap-1">
                    <button
                      type="button"
                      onClick={() => openEdit(goal)}
                      className="rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-400 hover:text-white"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => void remove(goal)}
                      className="rounded-lg p-1.5 text-slate-500 hover:bg-red-500/10 hover:text-red-300"
                      aria-label="Delete goal"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="mb-2 flex items-baseline justify-between gap-3">
                  <p className="text-xl font-bold text-white">
                    {formatMoney(goal.current_amount, goal.currency)}
                    <span className="ml-1.5 text-sm font-normal text-slate-500">
                      of {formatMoney(goal.target_amount, goal.currency)}
                    </span>
                  </p>
                  <span className="text-xs font-semibold text-slate-400">
                    {formatPercent(goal.percentage_completed)}
                  </span>
                </div>
                <ProgressBar value={goal.percentage_completed} tone="violet" />

                <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
                  <span>
                    Remaining:{" "}
                    <span className="font-semibold text-slate-300">
                      {formatMoney(goal.remaining_amount, goal.currency)}
                    </span>
                  </span>
                  {goal.target_date && (
                    <span className="inline-flex items-center gap-1.5">
                      <CalendarDays className="h-3.5 w-3.5" />
                      {formatDate(goal.target_date)}
                      {daysLeft !== null && goal.status === "active" && (
                        <span className={daysLeft < 0 ? "text-red-300" : "text-slate-500"}>
                          ({daysLeft < 0 ? "overdue" : `${daysLeft}d left`})
                        </span>
                      )}
                    </span>
                  )}
                </div>

                {goal.status === "active" && (
                  <div className="mt-4 flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        setContribGoal(goal);
                        setContribAmount("");
                        setContribDate(new Date().toISOString().slice(0, 10));
                        setContribNotes("");
                        setContribError(null);
                      }}
                    >
                      <Plus className="h-3.5 w-3.5" /> Contribute
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => void setStatus(goal, "cancelled")}>
                      Mark done
                    </Button>
                  </div>
                )}

                {goal.contributions.length > 0 && (
                  <div className="mt-4 space-y-1.5 border-t border-slate-800/70 pt-4">
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Recent contributions
                    </p>
                    {goal.contributions
                      .slice(-4)
                      .reverse()
                      .map((contribution) => (
                        <div
                          key={contribution.id}
                          className="flex items-center justify-between gap-2 text-xs"
                        >
                          <span className="text-slate-500">{formatDate(contribution.date)}</span>
                          <span className="flex items-center gap-2">
                            <span className="font-semibold text-emerald-300">
                              +{formatMoney(contribution.amount, goal.currency)}
                            </span>
                            <button
                              type="button"
                              onClick={() => void removeContribution(goal, contribution.id)}
                              className="text-slate-600 hover:text-red-300"
                              aria-label="Remove contribution"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </span>
                        </div>
                      ))}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Target className="h-6 w-6" />}
            title="No goals yet"
            description={`Create your first savings goal — e.g. an emergency fund or a laptop — in ${currency}.`}
            action={
              <Button size="sm" onClick={openCreate}>
                <Plus className="h-4 w-4" /> New goal
              </Button>
            }
          />
        </Card>
      )}

      {/* Create / edit modal */}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Edit goal" : "Create goal"}
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="goal-form" loading={saving}>
              {editing ? "Save changes" : "Create goal"}
            </Button>
          </>
        }
      >
        <form id="goal-form" onSubmit={submit} className="space-y-4">
          <Field label="Goal title" required>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Emergency fund"
              required
            />
          </Field>
          <Field label="Description">
            <Textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional details"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={`Target amount (${currencySymbol(currency)})`} required>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={targetAmount}
                onChange={(e) => setTargetAmount(e.target.value)}
                placeholder="0.00"
                required
              />
            </Field>
            <Field label="Target date">
              <Input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
              />
            </Field>
          </div>
          {formError && <ErrorBanner message={formError} />}
        </form>
      </Modal>

      {/* Contribute modal */}
      <Modal
        open={contribGoal !== null}
        onClose={() => setContribGoal(null)}
        title={`Contribute to ${contribGoal?.title ?? "goal"}`}
        subtitle={
          activeGoal
            ? `Currently ${formatMoney(activeGoal.current_amount, activeGoal.currency)} of ${formatMoney(activeGoal.target_amount, activeGoal.currency)}`
            : undefined
        }
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setContribGoal(null)}>
              Cancel
            </Button>
            <Button type="submit" form="contribution-form" loading={contribSaving}>
              Record contribution
            </Button>
          </>
        }
      >
        <form id="contribution-form" onSubmit={submitContribution} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label={`Amount (${currencySymbol(currency)})`} required>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={contribAmount}
                onChange={(e) => setContribAmount(e.target.value)}
                placeholder="0.00"
                required
              />
            </Field>
            <Field label="Date" required>
              <Input
                type="date"
                value={contribDate}
                onChange={(e) => setContribDate(e.target.value)}
                required
              />
            </Field>
          </div>
          <Field label="Notes">
            <Input
              value={contribNotes}
              onChange={(e) => setContribNotes(e.target.value)}
              placeholder="Optional note"
            />
          </Field>
          {contribError && <ErrorBanner message={contribError} />}
        </form>
      </Modal>
    </div>
  );
}
