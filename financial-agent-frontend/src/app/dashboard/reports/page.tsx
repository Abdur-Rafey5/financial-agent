"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3, CalendarRange, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import { reportsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ReportAnalytics } from "@/lib/types";
import {
  Card,
  CardHeader,
  ErrorBanner,
  Field,
  Input,
  LoadingBlock,
  SectionTitle,
  StatCard,
} from "@/components/ui";
import { BarList, DonutChart, LineChart } from "@/components/charts";
import { PageHeader } from "@/components/app-shell";
import { currencySymbol, formatMoney, formatPercent, todayISO } from "@/lib/format";

function monthsAgoISO(months: number): string {
  const now = new Date();
  now.setMonth(now.getMonth() - months);
  now.setDate(1);
  const offset = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return offset.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const { profile } = useAuth();
  const currency = profile?.currency ?? "PKR";

  const [start, setStart] = useState(monthsAgoISO(5));
  const [end, setEnd] = useState(todayISO());
  const [report, setReport] = useState<ReportAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (startDate: string, endDate: string) => {
    setLoading(true);
    setError(null);
    try {
      setReport(await reportsApi.analytics({ start_date: startDate, end_date: endDate }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the report.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(start, end);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const apply = () => {
    void load(start, end);
  };

  return (
    <div>
      <PageHeader
        icon={<BarChart3 className="h-6 w-6" />}
        title="Reports"
        description="Income, expenses and savings trends for any period — computed from your records."
      />

      <Card className="mb-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <Field label="From">
            <Input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="sm:w-44"
            />
          </Field>
          <Field label="To">
            <Input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="sm:w-44"
            />
          </Field>
          <button
            type="button"
            onClick={apply}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-500"
          >
            <CalendarRange className="h-4 w-4" /> Apply
          </button>
        </div>
      </Card>

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} onRetry={apply} />
        </div>
      )}

      {loading || !report ? (
        <LoadingBlock label="Building report…" />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total Income"
              value={formatMoney(report.total_income, currency)}
              icon={<TrendingUp className="h-5 w-5" />}
              tone="emerald"
            />
            <StatCard
              label="Total Expenses"
              value={formatMoney(report.total_expenses, currency)}
              icon={<TrendingDown className="h-5 w-5" />}
              tone="red"
            />
            <StatCard
              label="Net Savings"
              value={formatMoney(report.net_savings, currency)}
              sub={`Savings rate ${formatPercent(report.savings_rate_pct)}`}
              icon={<Wallet className="h-5 w-5" />}
              tone="indigo"
            />
            <StatCard
              label="Avg Monthly Expenses"
              value={formatMoney(report.average_monthly_expenses, currency)}
              sub={report.top_expense_category ? `Top: ${report.top_expense_category}` : undefined}
              tone="sky"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader
                title="Monthly Trend"
                subtitle={`Income vs expenses — ${report.months} month${report.months === 1 ? "" : "s"}`}
              />
              {report.monthly_trend.length ? (
                <LineChart
                  labels={report.monthly_trend.map((point) => point.month)}
                  series={[
                    {
                      name: "Income",
                      color: "#10b981",
                      data: report.monthly_trend.map((point) => point.income),
                    },
                    {
                      name: "Expenses",
                      color: "#ef4444",
                      data: report.monthly_trend.map((point) => point.expense),
                    },
                  ]}
                  formatValue={(value) => currencySymbol(currency) + Math.round(value).toLocaleString("en-US")}
                />
              ) : (
                <p className="py-12 text-center text-sm text-slate-500">No data for this period.</p>
              )}
            </Card>

            <Card>
              <CardHeader title="Expense Breakdown" subtitle="Where the money went (top categories)" />
              {report.category_breakdown.length ? (
                <DonutChart
                  items={report.category_breakdown
                    .slice(0, 8)
                    .map((item) => ({ label: item.label, value: item.amount, color: item.color }))}
                  centerLabel="Expenses"
                  centerValue={currencySymbol(currency) + Math.round(report.total_expenses).toLocaleString("en-US")}
                />
              ) : (
                <p className="py-12 text-center text-sm text-slate-500">No expenses in this period.</p>
              )}
            </Card>

            <Card>
              <CardHeader title="Expenses by Category" />
              <BarList
                items={report.category_breakdown.map((item) => ({
                  label: `${item.label} · ${item.percentage.toFixed(1)}%`,
                  value: item.amount,
                  color: item.color,
                }))}
                currencySymbol={currencySymbol(currency)}
              />
            </Card>

            <Card>
              <CardHeader title="Income by Category" />
              <BarList
                items={report.income_breakdown.map((item) => ({
                  label: `${item.label} · ${item.percentage.toFixed(1)}%`,
                  value: item.amount,
                  color: item.color,
                }))}
                currencySymbol={currencySymbol(currency)}
                emptyLabel="No income recorded in this period."
              />
            </Card>
          </div>

          {report.monthly_trend.length > 0 && (
            <Card>
              <CardHeader title="Month by Month" />
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                      <th className="pb-2">Month</th>
                      <th className="pb-2 text-right">Income</th>
                      <th className="pb-2 text-right">Expenses</th>
                      <th className="pb-2 text-right">Net Savings</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {report.monthly_trend.map((point) => (
                      <tr key={point.month_start}>
                        <td className="py-2.5 font-medium text-slate-200">{point.month}</td>
                        <td className="py-2.5 text-right text-emerald-300">
                          {formatMoney(point.income, currency)}
                        </td>
                        <td className="py-2.5 text-right text-red-300">
                          {formatMoney(point.expense, currency)}
                        </td>
                        <td
                          className={`py-2.5 text-right font-semibold ${
                            point.net_savings >= 0 ? "text-emerald-300" : "text-red-300"
                          }`}
                        >
                          {formatMoney(point.net_savings, currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-5">
                <SectionTitle>Period: {report.start_date} — {report.end_date}</SectionTitle>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
