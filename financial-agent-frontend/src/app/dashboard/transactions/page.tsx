"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  Pencil,
  Plus,
  Receipt,
  Trash2,
} from "lucide-react";
import { categoryApi, expenseApi, incomeApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  ExpenseCategory,
  ExpenseRecord,
  IncomeCategory,
  IncomeRecord,
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
  SectionTitle,
  Select,
  StatCard,
  Textarea,
} from "@/components/ui";
import { PageHeader } from "@/components/app-shell";
import { currencySymbol, formatMoney, todayISO } from "@/lib/format";

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

type Mode = "income" | "expense";

interface IncomeForm {
  amount: string;
  currency: string;
  date: string;
  source: string;
  income_type: IncomeType;
  notes: string;
}

interface ExpenseForm {
  amount: string;
  currency: string;
  date: string;
  description: string;
  category_id: string;
  notes: string;
}

export default function TransactionsPage() {
  const { profile } = useAuth();
  const profileCurrency = profile?.currency ?? "PKR";

  const [income, setIncome] = useState<IncomeRecord[]>([]);
  const [expenses, setExpenses] = useState<ExpenseRecord[]>([]);
  const [incomeTotal, setIncomeTotal] = useState(0);
  const [expenseTotal, setExpenseTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [tab, setTab] = useState<Mode>("expense");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [incomeList, expenseList] = await Promise.all([
        incomeApi.list({ search: search || undefined, limit: 200 }),
        expenseApi.list({ search: search || undefined, limit: 200 }),
      ]);
      setIncome(incomeList.items);
      setExpenses(expenseList.items);
      setIncomeTotal(incomeList.total_amount);
      setExpenseTotal(expenseList.total_amount);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transactions.");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    void load();
  }, [load]);

  // ── Modal state ─────────────────────────────────────────────────
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [incomeCategories, setIncomeCategories] = useState<IncomeCategory[]>([]);

  const [incomeForm, setIncomeForm] = useState<IncomeForm>({
    amount: "",
    currency: profileCurrency,
    date: todayISO(),
    source: "",
    income_type: "salary",
    notes: "",
  });
  const [expenseForm, setExpenseForm] = useState<ExpenseForm>({
    amount: "",
    currency: profileCurrency,
    date: todayISO(),
    description: "",
    category_id: "",
    notes: "",
  });

  const openModal = async (mode: Mode, record?: IncomeRecord | ExpenseRecord) => {
    setTab(mode);
    setEditing(record ? record.id : null);
    setFormError(null);
    if (mode === "income") {
      setIncomeForm(
        record
          ? {
              amount: String((record as IncomeRecord).amount),
              currency: record.currency,
              date: record.date,
              source: (record as IncomeRecord).source,
              income_type: (record as IncomeRecord).income_type as IncomeType,
              notes: (record as IncomeRecord).notes ?? "",
            }
          : {
              amount: "",
              currency: profileCurrency,
              date: todayISO(),
              source: "",
              income_type: "salary",
              notes: "",
            }
      );
    } else {
      setExpenseForm(
        record
          ? {
              amount: String((record as ExpenseRecord).amount),
              currency: record.currency,
              date: record.date,
              description: (record as ExpenseRecord).description,
              category_id: (record as ExpenseRecord).category_id ?? "",
              notes: (record as ExpenseRecord).notes ?? "",
            }
          : {
              amount: "",
              currency: profileCurrency,
              date: todayISO(),
              description: "",
              category_id: "",
              notes: "",
            }
      );
    }
    setOpen(true);
    if (!categories.length || !incomeCategories.length) {
      try {
        const [ecats, icats] = await Promise.all([
          categoryApi.expenseCategories(),
          categoryApi.incomeCategories(),
        ]);
        setCategories(ecats);
        setIncomeCategories(icats);
      } catch {
        /* categories optional */
      }
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const value = parseFloat(tab === "income" ? incomeForm.amount : expenseForm.amount);
    if (!value || value <= 0) {
      setFormError("Enter a valid amount.");
      return;
    }
    setSaving(true);
    try {
      if (tab === "income") {
        const payload = {
          amount: value,
          currency: incomeForm.currency,
          date: incomeForm.date,
          source: incomeForm.source,
          income_type: incomeForm.income_type,
          notes: incomeForm.notes || undefined,
        };
        if (editing) await incomeApi.update(editing, payload);
        else await incomeApi.create(payload);
      } else {
        const payload = {
          amount: value,
          currency: expenseForm.currency,
          date: expenseForm.date,
          description: expenseForm.description,
          category_id: expenseForm.category_id || undefined,
          notes: expenseForm.notes || undefined,
        };
        if (editing) await expenseApi.update(editing, payload);
        else await expenseApi.create(payload);
      }
      setOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to save the record.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (mode: Mode, id: string) => {
    try {
      if (mode === "income") await incomeApi.delete(id);
      else await expenseApi.delete(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete the record.");
    }
  };

  const items =
    tab === "income"
      ? income.map((r) => ({
          id: r.id,
          when: r.date,
          title: r.source,
          amount: r.amount,
          type: "income" as const,
          tag: r.income_type.replace(/_/g, " "),
        }))
      : expenses.map((r) => ({
          id: r.id,
          when: r.date,
          title: r.description,
          amount: r.amount,
          type: "expense" as const,
          tag: r.category_name ?? "Uncategorized",
        }));
  items.sort((a, b) => b.when.localeCompare(a.when));

  return (
    <div>
      <PageHeader
        icon={<Receipt className="h-6 w-6" />}
        title="Transactions"
        description="Record and manage every rupee that comes in and goes out."
        action={
          <Button onClick={() => void openModal(tab)}>
            <Plus className="h-4 w-4" /> Add {tab}
          </Button>
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Total Income"
          value={formatMoney(incomeTotal, profileCurrency)}
          icon={<ArrowUpCircle className="h-5 w-5" />}
          tone="emerald"
        />
        <StatCard
          label="Total Expenses"
          value={formatMoney(expenseTotal, profileCurrency)}
          icon={<ArrowDownCircle className="h-5 w-5" />}
          tone="red"
        />
        <StatCard
          label="Net"
          value={formatMoney(incomeTotal - expenseTotal, profileCurrency)}
          icon={<Receipt className="h-5 w-5" />}
          tone="indigo"
        />
      </div>

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} onRetry={() => void load()} />
        </div>
      )}

      <Card>
        <CardHeader
          title={
            <div className="flex items-center gap-2">
              <div className="flex rounded-xl border border-slate-700/80 bg-slate-900/60 p-1">
                <button
                  type="button"
                  onClick={() => setTab("expense")}
                  className={
                    tab === "expense"
                      ? "rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-semibold text-red-200"
                      : "rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-400"
                  }
                >
                  Expenses
                </button>
                <button
                  type="button"
                  onClick={() => setTab("income")}
                  className={
                    tab === "income"
                      ? "rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs font-semibold text-emerald-200"
                      : "rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-400"
                  }
                >
                  Income
                </button>
              </div>
            </div>
          }
          action={
            <Input
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-44 sm:w-64"
            />
          }
        />

        {loading ? (
          <LoadingBlock label="Loading transactions…" />
        ) : items.length ? (
          <div className="divide-y divide-slate-800/60">
            {items.map((item) => (
              <div
                key={`${item.type}-${item.id}`}
                className="flex items-center justify-between gap-4 py-3"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <Badge tone={item.type === "income" ? "emerald" : "red"}>{item.tag}</Badge>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-white">{item.title}</p>
                    <p className="text-xs text-slate-500">{item.when}</p>
                  </div>
                </div>
                <div className="flex flex-shrink-0 items-center gap-1.5">
                  <span
                    className={
                      item.type === "income"
                        ? "text-sm font-semibold text-emerald-300"
                        : "text-sm font-semibold text-red-300"
                    }
                  >
                    {item.type === "income" ? "+" : "-"}
                    {formatMoney(item.amount, profileCurrency)}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      const record =
                        item.type === "income"
                          ? income.find((r) => r.id === item.id)
                          : expenses.find((r) => r.id === item.id);
                      if (record) void openModal(item.type, record);
                    }}
                    className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-slate-800 hover:text-white"
                    aria-label="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => void remove(item.type, item.id)}
                    className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-red-500/10 hover:text-red-300"
                    aria-label="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Receipt className="h-6 w-6" />}
            title={search ? "No matches" : `No ${tab} records yet`}
            description={
              search
                ? "Try a different search term."
                : "Add your first record so your dashboard and AI insights stay accurate."
            }
            action={
              !search && (
                <Button size="sm" onClick={() => void openModal(tab)}>
                  <Plus className="h-4 w-4" /> Add {tab}
                </Button>
              )
            }
          />
        )}
      </Card>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={`${editing ? "Edit" : "Add"} ${tab} record`}
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="tx-form" loading={saving}>
              {editing ? "Save changes" : "Add record"}
            </Button>
          </>
        }
      >
        <form id="tx-form" onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount" required>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={tab === "income" ? incomeForm.amount : expenseForm.amount}
                onChange={(e) =>
                  tab === "income"
                    ? setIncomeForm({ ...incomeForm, amount: e.target.value })
                    : setExpenseForm({ ...expenseForm, amount: e.target.value })
                }
                placeholder="0.00"
                required
              />
            </Field>
            <Field label="Currency">
              <Select
                value={tab === "income" ? incomeForm.currency : expenseForm.currency}
                onChange={(e) =>
                  tab === "income"
                    ? setIncomeForm({ ...incomeForm, currency: e.target.value })
                    : setExpenseForm({ ...expenseForm, currency: e.target.value })
                }
              >
                {Array.from(new Set([profileCurrency, ...CURRENCIES])).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <Field label="Date" required>
            <Input
              type="date"
              value={tab === "income" ? incomeForm.date : expenseForm.date}
              onChange={(e) =>
                tab === "income"
                  ? setIncomeForm({ ...incomeForm, date: e.target.value })
                  : setExpenseForm({ ...expenseForm, date: e.target.value })
              }
              required
            />
          </Field>

          {tab === "income" ? (
            <>
              <Field label="Source" required>
                <Input
                  value={incomeForm.source}
                  onChange={(e) => setIncomeForm({ ...incomeForm, source: e.target.value })}
                  placeholder="e.g. Monthly salary"
                  required
                />
              </Field>
              <Field label="Income type">
                <Select
                  value={incomeForm.income_type}
                  onChange={(e) =>
                    setIncomeForm({
                      ...incomeForm,
                      income_type: e.target.value as IncomeType,
                    })
                  }
                >
                  {INCOME_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </>
          ) : (
            <>
              <Field label="Description" required>
                <Input
                  value={expenseForm.description}
                  onChange={(e) =>
                    setExpenseForm({ ...expenseForm, description: e.target.value })
                  }
                  placeholder="e.g. Weekly groceries"
                  required
                />
              </Field>
              <Field label="Category">
                <Select
                  value={expenseForm.category_id}
                  onChange={(e) =>
                    setExpenseForm({ ...expenseForm, category_id: e.target.value })
                  }
                >
                  <option value="">Uncategorized</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </>
          )}

          <Field label="Notes">
            <Textarea
              rows={2}
              value={tab === "income" ? incomeForm.notes : expenseForm.notes}
              onChange={(e) =>
                tab === "income"
                  ? setIncomeForm({ ...incomeForm, notes: e.target.value })
                  : setExpenseForm({ ...expenseForm, notes: e.target.value })
              }
            />
          </Field>

          {formError && <ErrorBanner message={formError} />}
          <SectionTitle>
            {editing ? "Changes are saved immediately." : "Records update your dashboard instantly."}
          </SectionTitle>
        </form>
      </Modal>
    </div>
  );
}
