"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Building,
  Lightbulb,
  PiggyBank,
  Plus,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { categoryApi, dashboardApi, expenseApi, incomeApi } from "@/lib/api";
import type {
  DashboardSummary,
  ExpenseCategory,
  IncomeCategory,
  IncomeType,
} from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  LoadingBlock,
  Modal,
  Select,
  StatCard,
  Textarea,
} from "@/components/ui";
import { BarList, LineChart } from "@/components/charts";
import { PageHeader } from "@/components/app-shell";
import {
  currencySymbol,
  formatDate,
  formatMoney,
  formatMonth,
  formatPercent,
  todayISO,
} from "@/lib/format";

const INCOME_TYPES: { value: IncomeType; label: string }[] = [
  { value: "salary", label: "Salary" },
  { value: "allowance", label: "Allowance" },
  { value: "freelance", label: "Freelance" },
  { value: "business_revenue", label: "Business Revenue" },
  { value: "investment", label: "Investment" },
  { value: "gift", label: "Gift" },
  { value: "refund", label: "Refund" },
  { value: "other", label: "Other" },
];

const CURRENCIES = ["PKR", "USD", "EUR", "GBP", "INR", "AED", "SAR"];

type MetricRow = { label: string; value: ReactNode };

function categoryRows(
  category: DashboardSummary["category"],
  metrics: Record<string, number | boolean>,
  currency: string
): MetricRow[] {
  const has = (key: string) => Object.prototype.hasOwnProperty.call(metrics, key);
  const num = (key: string) => Number(metrics[key] ?? 0);
  const rows: MetricRow[] = [];

  if (category === "student") {
    if (has("safe_daily_spend"))
      rows.push({ label: "Safe Daily Spend", value: formatMoney(num("safe_daily_spend"), currency) });
    if (has("allowance_used_pct"))
      rows.push({ label: "Allowance Used", value: formatPercent(num("allowance_used_pct")) });
    if (has("days_left_in_month"))
      rows.push({ label: "Days Left in Month", value: String(num("days_left_in_month")) });
  } else if (category === "employee") {
    if (has("recommended_savings_20pct"))
      rows.push({
        label: "Recommended Savings (20%)",
        value: formatMoney(num("recommended_savings_20pct"), currency),
      });
    if (has("savings_target_met"))
      rows.push({
        label: "Savings Target Met",
        value: metrics.savings_target_met ? "Yes" : "Not yet",
      });
    if (has("disposable_income"))
      rows.push({ label: "Disposable Income", value: formatMoney(num("disposable_income"), currency) });
  } else if (category === "businessman") {
    if (has("net_cash_flow"))
      rows.push({ label: "Net Cash Flow", value: formatMoney(num("net_cash_flow"), currency) });
    if (has("gross_margin_pct"))
      rows.push({ label: "Gross Margin", value: formatPercent(num("gross_margin_pct")) });
    if (has("available_capital"))
      rows.push({ label: "Available Capital", value: formatMoney(num("available_capital"), currency) });
  }

  return rows;
}

export default function OverviewPage() {
  const { profile } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await dashboardApi.summary());
    } catch (e: any) {
      setError(e?.message || "Failed to load your dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // ---------------------------------------------------------- quick add
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [expenseCats, setExpenseCats] = useState<ExpenseCategory[]>([]);
  const [incomeCats, setIncomeCats] = useState<IncomeCategory[]>([]);

  const [txType, setTxType] = useState<"income" | "expense">("expense");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("PKR");
  const [date, setDate] = useState(todayISO());
  const [description, setDescription] = useState("");
  const [source, setSource] = useState("");
  const [incomeType, setIncomeType] = useState<IncomeType>("salary");
  const [categoryId, setCategoryId] = useState("");
  const [notes, setNotes] = useState("");

  const profileCurrency = profile?.currency ?? "PKR";
  const currencyOptions = Array.from(new Set([profileCurrency, ...CURRENCIES]));
  const categories = txType === "expense" ? expenseCats : incomeCats;

  const openModal = () => {
    setTxType("expense");
    setAmount("");
    setCurrency(profileCurrency);
    setDate(todayISO());
    setDescription("");
    setSource("");
    setIncomeType("salary");
    setCategoryId("");
    setNotes("");
    setFormError(null);
    setOpen(true);
    void (async () => {
      try {
        const [e, i] = await Promise.all([
          categoryApi.expenseCategories(),
          categoryApi.incomeCategories(),
        ]);
        setExpenseCats(e);
        setIncomeCats(i);
      } catch {
        /* categories are optional for the quick-add helper */
      }
    })();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const value = parseFloat(amount);
    if (!value || value <= 0) {
      setFormError("Enter a valid amount.");
      return;
    }
    if (txType === "expense" && !categoryId) {
      setFormError("Select a category.");
      return;
    }
    setSaving(true);
    try {
      if (txType === "expense") {
        await expenseApi.create({
          amount: value,
          currency,
          date,
          description,
          category_id: categoryId,
          notes: notes || undefined,
        });
      } else {
        await incomeApi.create({
          amount: value,
          currency,
          date,
          source,
          income_type: incomeType,
          category_id: categoryId || undefined,
          notes: notes || undefined,
        });
      }
      setOpen(false);
      await load();
    } catch (err: any) {
      setFormError(err?.message || "Failed to save transaction.");
    } finally {
      setSaving(false);
    }
  };

  // ---------------------------------------------------------- render
  const trend = summary?.trend ?? [];
  const hasNet = trend.some((p) => p.net !== 0);
  const labels = trend.map((p) => formatMonth(p.month));
  const series = [
    { name: "Income", color: "#10b981", data: trend.map((p) => p.income) },
    { name: "Expenses", color: "#ef4444", data: trend.map((p) => p.expenses) },
    ...(hasNet ? [{ name: "Net", color: "#6366f1", data: trend.map((p) => p.net) }] : []),
  ];

  return (
    <div>
      <PageHeader
        title="Overview"
        description={
          summary
            ? `Reporting period: ${formatDate(summary.period_start)} – ${formatDate(summary.period_end)}`
            : "Your financial snapshot."
        }
        action={
          <Button onClick={openModal}>
            <Plus className="w-4 h-4" /> Quick add
          </Button>
        }
      />

      {loading && !summary ? (
        <LoadingBlock label="Loading your dashboard…" />
      ) : error && !summary ? (
        <ErrorBanner message={error} onRetry={() => void load()} />
      ) : summary ? (
        <div className="space-y-6">
          {error && <ErrorBanner message={error} onRetry={() => void load()} />}

          {/* Stat cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Income (This Month)"
              value={formatMoney(summary.total_income_this_month, summary.currency)}
              icon={<TrendingUp className="w-5 h-5" />}
              tone="emerald"
            />
            <StatCard
              label="Expenses (This Month)"
              value={formatMoney(summary.total_expenses_this_month, summary.currency)}
              sub={`${summary.expense_change_pct >= 0 ? "+" : ""}${formatPercent(
                summary.expense_change_pct
              )} vs ${formatMoney(summary.previous_month_expenses, summary.currency)} last month`}
              icon={<TrendingDown className="w-5 h-5" />}
              tone="red"
            />
            <StatCard
              label="Net Savings"
              value={formatMoney(summary.net_savings_this_month, summary.currency)}
              sub={`Savings rate ${formatPercent(summary.savings_rate_pct)}`}
              icon={<PiggyBank className="w-5 h-5" />}
              tone="indigo"
            />
            <Link href="/dashboard/recommendations" className="block">
              <StatCard
                label="New Insights"
                value={summary.unread_recommendations_count}
                sub="Unread recommendations"
                icon={<Sparkles className="w-5 h-5" />}
                tone="violet"
              />
            </Link>
          </div>

          {/* Trend + top categories */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2">
              <CardHeader title="Income vs Expenses" subtitle="Monthly trend" />
              {trend.length ? (
                <LineChart series={series} labels={labels} height={240} />
              ) : (
                <EmptyState
                  title="No trend data yet"
                  description="Record income and expenses to see your monthly trend."
                />
              )}
            </Card>

            <Card>
              <CardHeader title="Top Expense Categories" />
              <BarList
                items={(summary.top_expense_categories ?? []).map((c) => ({
                  label: `${c.name} · ${c.percentage.toFixed(1)}%`,
                  value: c.amount,
                  color: c.color || undefined,
                }))}
                currencySymbol={currencySymbol(summary.currency)}
              />
            </Card>
          </div>

          {/* Category insight + goals/budgets */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2">
              <CardHeader
                title={
                  <span className="inline-flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-amber-300" />
                    {summary.category
                      ? `${summary.category[0].toUpperCase()}${summary.category.slice(1)} Insights`
                      : "Insights"}
                  </span>
                }
              />
              {(() => {
                const rows = categoryRows(
                  summary.category,
                  summary.category_metrics ?? {},
                  summary.currency
                );
                if (!rows.length) {
                  return (
                    <p className="text-sm text-slate-500 py-4">
                      No category-specific metrics available yet.
                    </p>
                  );
                }
                return (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {rows.map((r) => (
                      <div key={r.label} className="rounded-xl bg-slate-900/40 border border-white/5 p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                          {r.label}
                        </p>
                        <p className="text-lg font-bold text-white mt-1.5">{r.value}</p>
                      </div>
                    ))}
                  </div>
                );
              })()}
              <p className="text-[11px] text-slate-500 mt-4">
                These figures are computed by the backend from your transaction history and profile.
              </p>
            </Card>

            <div className="space-y-4">
              <Link href="/dashboard/goals" className="block">
                <StatCard
                  label="Active Goals"
                  value={summary.active_goals_count}
                  sub="View goals"
                  icon={<Target className="w-5 h-5" />}
                  tone="sky"
                />
              </Link>
              <Link href="/dashboard/budgets" className="block">
                <StatCard
                  label="Active Budgets"
                  value={summary.active_budgets_count}
                  sub="View budgets"
                  icon={<Wallet className="w-5 h-5" />}
                  tone="amber"
                />
              </Link>
            </div>
          </div>

          {/* Business snapshot */}
          {summary.category === "businessman" && summary.business && (
            <Link href="/dashboard/business" className="block">
              <Card hover>
                <CardHeader
                  title={
                    <span className="inline-flex items-center gap-2">
                      <Building className="w-4 h-4 text-emerald-300" />
                      {summary.business.name}
                      {summary.business.industry && (
                        <span className="text-xs font-normal text-slate-500">
                          {summary.business.industry}
                        </span>
                      )}
                    </span>
                  }
                  subtitle="Available capital this period"
                  action={<ArrowUpRight className="w-4 h-4 text-slate-400" />}
                />
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Available Capital
                    </p>
                    <p className="mt-1 text-lg font-bold text-emerald-300">
                      {formatMoney(
                        summary.business.available_capital,
                        summary.business.currency
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Net Cash Flow
                    </p>
                    <p className="mt-1 text-lg font-bold text-white">
                      {formatMoney(Number(summary.category_metrics.net_cash_flow ?? 0), summary.currency)}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Gross Margin
                    </p>
                    <p className="mt-1 text-lg font-bold text-indigo-300">
                      {formatPercent(Number(summary.category_metrics.gross_margin_pct ?? 0))}
                    </p>
                  </div>
                </div>
              </Card>
            </Link>
          )}

          {/* Recent transactions */}
          <Card>
            <CardHeader
              title="Recent Transactions"
              action={
                <Link
                  href="/dashboard/transactions"
                  className="text-xs font-semibold text-indigo-400 hover:text-indigo-300"
                >
                  View all
                </Link>
              }
            />
            {summary.recent_transactions?.length ? (
              <div className="divide-y divide-slate-800/60">
                {summary.recent_transactions.map((tx) => (
                  <div key={tx.id} className="py-3 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <Badge tone={tx.type === "income" ? "emerald" : "red"}>{tx.type}</Badge>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-white truncate">{tx.description}</p>
                        <p className="text-xs text-slate-500">
                          {tx.category || "Uncategorized"} · {formatDate(tx.date)}
                        </p>
                      </div>
                    </div>
                    <span
                      className={
                        tx.type === "income"
                          ? "text-sm font-semibold text-emerald-300 whitespace-nowrap"
                          : "text-sm font-semibold text-red-300 whitespace-nowrap"
                      }
                    >
                      {tx.type === "income" ? "+" : "-"}
                      {formatMoney(tx.amount, summary.currency)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No transactions yet"
                description="Use Quick add to record your first income or expense."
                action={
                  <Button onClick={openModal} size="sm">
                    <Plus className="w-4 h-4" /> Quick add
                  </Button>
                }
              />
            )}
          </Card>
        </div>
      ) : null}

      {/* Quick add modal */}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Quick add transaction"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" form="quick-add-form" loading={saving}>
              Save
            </Button>
          </>
        }
      >
        <form id="quick-add-form" onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-2 p-1 bg-slate-900/60 rounded-xl border border-slate-700/80">
            <button
              type="button"
              onClick={() => {
                setTxType("expense");
                setCategoryId("");
              }}
              className={
                txType === "expense"
                  ? "py-2 text-xs font-semibold rounded-lg bg-red-500/20 text-red-200 border border-red-500/30"
                  : "py-2 text-xs font-semibold rounded-lg text-slate-400"
              }
            >
              Expense
            </button>
            <button
              type="button"
              onClick={() => {
                setTxType("income");
                setCategoryId("");
              }}
              className={
                txType === "income"
                  ? "py-2 text-xs font-semibold rounded-lg bg-emerald-500/20 text-emerald-200 border border-emerald-500/30"
                  : "py-2 text-xs font-semibold rounded-lg text-slate-400"
              }
            >
              Income
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount">
              <Input
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0"
                required
              />
            </Field>
            <Field label="Currency">
              <Select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {currencyOptions.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <Field label="Date">
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </Field>

          {txType === "expense" ? (
            <Field label="Description">
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Groceries"
                required
              />
            </Field>
          ) : (
            <>
              <Field label="Source">
                <Input
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  placeholder="e.g. Monthly salary"
                  required
                />
              </Field>
              <Field label="Income type">
                <Select
                  value={incomeType}
                  onChange={(e) => setIncomeType(e.target.value as IncomeType)}
                >
                  {INCOME_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </>
          )}

          <Field label="Category" hint={txType === "expense" ? "Required" : "Optional"}>
            <Select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              required={txType === "expense"}
            >
              <option value="">{txType === "expense" ? "Select a category" : "Uncategorized"}</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Notes" hint="Optional">
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          </Field>

          {formError && <ErrorBanner message={formError} />}
        </form>
      </Modal>
    </div>
  );
}
