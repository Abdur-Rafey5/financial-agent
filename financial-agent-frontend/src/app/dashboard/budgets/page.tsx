"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Plus, Trash2, Wallet, X } from "lucide-react";
import { budgetsApi, categoryApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Budget, ExpenseCategory } from "@/lib/types";
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
  Select,
} from "@/components/ui";
import { PageHeader } from "@/components/app-shell";
import { addDaysISO, currencySymbol, formatDate, formatMoney, formatPercent, todayISO } from "@/lib/format";

interface AllocationRow {
  category_id: string;
  limit_amount: string;
}

export default function BudgetsPage() {
  const { profile } = useAuth();
  const currency = profile?.currency ?? "PKR";

  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setBudgets(await budgetsApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load budgets.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // ── Create modal ────────────────────────────────────────────────
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);

  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState(todayISO().slice(0, 8) + "01");
  const [endDate, setEndDate] = useState(addDaysISO(todayISO(), 30));
  const [totalLimit, setTotalLimit] = useState("");
  const [allocations, setAllocations] = useState<AllocationRow[]>([]);

  const openModal = () => {
    const now = new Date();
    const first = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
    setName("");
    setStartDate(first);
    setEndDate(addDaysISO(first, 30));
    setTotalLimit("");
    setAllocations([]);
    setFormError(null);
    setOpen(true);
    void categoryApi
      .expenseCategories()
      .then(setCategories)
      .catch(() => undefined);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const limit = parseFloat(totalLimit);
    if (!limit || limit <= 0) {
      setFormError("Enter a valid total limit.");
      return;
    }
    if (new Date(endDate) < new Date(startDate)) {
      setFormError("End date must be on or after the start date.");
      return;
    }
    const rows = allocations.filter((row) => row.category_id && parseFloat(row.limit_amount) > 0);
    setSaving(true);
    try {
      await budgetsApi.create({
        name,
        start_date: startDate,
        end_date: endDate,
        total_limit: limit,
        currency,
        category_allocations: rows.map((row) => ({
          category_id: row.category_id,
          limit_amount: parseFloat(row.limit_amount),
        })),
      });
      setOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create the budget.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await budgetsApi.delete(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete the budget.");
    }
  };

  return (
    <div>
      <PageHeader
        icon={<Wallet className="h-6 w-6" />}
        title="Budgets"
        description="Set spending ceilings for periods and categories — progress updates as you record expenses."
        action={
          <Button onClick={openModal}>
            <Plus className="h-4 w-4" /> New budget
          </Button>
        }
      />

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} onRetry={() => void load()} />
        </div>
      )}

      {loading ? (
        <LoadingBlock label="Loading budgets…" />
      ) : budgets.length ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {budgets.map((budget) => (
            <Card key={budget.id} hover>
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-white">{budget.name}</h3>
                    <Badge tone={budget.is_active ? "emerald" : "slate"}>
                      {budget.is_active ? "active" : "ended"}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {formatDate(budget.start_date)} – {formatDate(budget.end_date)} ·{" "}
                    {budget.period_type}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void remove(budget.id)}
                  className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-red-500/10 hover:text-red-300"
                  aria-label="Delete budget"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>

              <div className="mb-2 flex items-baseline justify-between gap-3">
                <p className="text-xl font-bold text-white">
                  {formatMoney(budget.total_spent, budget.currency)}
                  <span className="ml-1.5 text-sm font-normal text-slate-500">
                    of {formatMoney(budget.total_limit, budget.currency)}
                  </span>
                </p>
                <span className="text-xs font-semibold text-slate-400">
                  {formatPercent(budget.usage_pct)}
                </span>
              </div>
              <ProgressBar value={budget.usage_pct} />
              <p className="mt-2 text-xs text-slate-500">
                Remaining:{" "}
                <span className={budget.remaining_amount >= 0 ? "text-emerald-300" : "text-red-300"}>
                  {formatMoney(budget.remaining_amount, budget.currency)}
                </span>
              </p>

              {budget.allocations.length > 0 && (
                <div className="mt-5 space-y-3 border-t border-slate-800/70 pt-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    Category allocations
                  </p>
                  {budget.allocations.map((allocation) => (
                    <div key={allocation.id}>
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="text-slate-300">{allocation.category_name}</span>
                        <span className="text-slate-400">
                          {formatMoney(allocation.spent_amount, budget.currency)} /{" "}
                          {formatMoney(allocation.limit_amount, budget.currency)} ·{" "}
                          {formatPercent(allocation.usage_pct)}
                        </span>
                      </div>
                      <ProgressBar value={allocation.usage_pct} />
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Wallet className="h-6 w-6" />}
            title="No budgets yet"
            description={`Create your first budget with a total limit and optional per-category limits in ${currency}.`}
            action={
              <Button size="sm" onClick={openModal}>
                <Plus className="h-4 w-4" /> New budget
              </Button>
            }
          />
        </Card>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Create budget"
        subtitle={`Limits are in ${currency}`}
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="budget-form" loading={saving}>
              Create budget
            </Button>
          </>
        }
      >
        <form id="budget-form" onSubmit={submit} className="space-y-4">
          <Field label="Budget name" required>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. November spending plan"
              required
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Start date" required>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </Field>
            <Field label="End date" required>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
            </Field>
          </div>
          <Field label="Total limit" required>
            <Input
              type="number"
              min="0"
              step="0.01"
              value={totalLimit}
              onChange={(e) => setTotalLimit(e.target.value)}
              placeholder="0.00"
              required
            />
          </Field>

          <div>
            <p className="mb-2 text-xs font-semibold text-slate-300">
              Category allocations <span className="font-normal text-slate-500">(optional)</span>
            </p>
            <div className="space-y-2">
              {allocations.map((row, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Select
                    value={row.category_id}
                    onChange={(e) =>
                      setAllocations(
                        allocations.map((r, i) =>
                          i === index ? { ...r, category_id: e.target.value } : r
                        )
                      )
                    }
                    className="flex-1"
                  >
                    <option value="">Select category</option>
                    {categories
                      .filter(
                        (c) =>
                          !allocations.some((r, i) => i !== index && r.category_id === c.id)
                      )
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                  </Select>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={row.limit_amount}
                    onChange={(e) =>
                      setAllocations(
                        allocations.map((r, i) =>
                          i === index ? { ...r, limit_amount: e.target.value } : r
                        )
                      )
                    }
                    placeholder={currencySymbol(currency)}
                    className="w-28"
                  />
                  <button
                    type="button"
                    onClick={() => setAllocations(allocations.filter((_, i) => i !== index))}
                    className="rounded-lg p-2 text-slate-500 hover:text-red-300"
                    aria-label="Remove allocation"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() =>
                  setAllocations([...allocations, { category_id: "", limit_amount: "" }])
                }
                disabled={
                  categories.length === 0 ||
                  allocations.length >= categories.length ||
                  allocations.some((r) => !r.category_id || parseInt(r.limit_amount || "0") <= 0)
                }
              >
                <Plus className="h-3.5 w-3.5" /> Add allocation
              </Button>
            </div>
          </div>

          {formError && <ErrorBanner message={formError} />}
        </form>
      </Modal>
    </div>
  );
}
