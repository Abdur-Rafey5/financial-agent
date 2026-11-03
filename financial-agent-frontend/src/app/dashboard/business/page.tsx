"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Building2, Plus, Sparkles, Trash2, TrendingUp } from "lucide-react";
import { businessApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { BusinessProfile, BusinessSummary, CashFlowResponse, Scenario, ScenarioResult } from "@/lib/types";
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
  ProgressBar,
  SectionTitle,
  StatCard,
  Textarea,
} from "@/components/ui";
import { BarList, LineChart } from "@/components/charts";
import { PageHeader } from "@/components/app-shell";
import { currencySymbol, formatMoney, formatPercent, formatNumber } from "@/lib/format";

const CURRENCIES = ["PKR", "USD", "EUR", "GBP", "INR", "AED", "SAR"];

interface ScenarioForm {
  title: string;
  scenario_type: string;
  description: string;
  initial_cost: string;
  expected_monthly_return: string;
  monthly_operating_cost: string;
  monthly_growth_pct: string;
  horizon_months: string;
}

const EMPTY_SCENARIO: ScenarioForm = {
  title: "",
  scenario_type: "investment",
  description: "",
  initial_cost: "",
  expected_monthly_return: "",
  monthly_operating_cost: "0",
  monthly_growth_pct: "0",
  horizon_months: "12",
};

export default function BusinessPage() {
  const { refreshProfile } = useAuth();

  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [summary, setSummary] = useState<BusinessSummary | null>(null);
  const [cashFlow, setCashFlow] = useState<CashFlowResponse | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const profileRes = await businessApi.getProfile();
      setProfile(profileRes);
      if (profileRes) {
        const [summaryRes, cashFlowRes, scenariosRes] = await Promise.all([
          businessApi.summary(),
          businessApi.cashFlow(6),
          businessApi.scenarios(),
        ]);
        setSummary(summaryRes);
        setCashFlow(cashFlowRes);
        setScenarios(scenariosRes);
      } else {
        setSummary(null);
        setCashFlow(null);
        setScenarios([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load business data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // ── Profile modal ───────────────────────────────────────────────
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [industry, setIndustry] = useState("");
  const [availableCapital, setAvailableCapital] = useState("");
  const [currencyChoice, setCurrencyChoice] = useState("PKR");
  const [description, setDescription] = useState("");

  const openProfileModal = (existing?: BusinessProfile | null) => {
    setBusinessName(existing?.business_name ?? "");
    setBusinessType(existing?.business_type ?? "");
    setIndustry(existing?.industry ?? "");
    setAvailableCapital(existing?.available_capital != null ? String(existing.available_capital) : "");
    setCurrencyChoice(existing?.currency ?? "PKR");
    setDescription(existing?.description ?? "");
    setProfileError(null);
    setProfileOpen(true);
  };

  const submitProfile = async (e: FormEvent) => {
    e.preventDefault();
    setProfileError(null);
    if (!businessName.trim()) {
      setProfileError("Business name is required.");
      return;
    }
    setProfileSaving(true);
    try {
      const payload = {
        business_name: businessName.trim(),
        business_type: businessType.trim() || undefined,
        industry: industry.trim() || undefined,
        available_capital: availableCapital ? parseFloat(availableCapital) : undefined,
        currency: currencyChoice,
        description: description.trim() || undefined,
      };
      if (profile) await businessApi.updateProfile(payload);
      else await businessApi.upsertProfile(payload);
      setProfileOpen(false);
      await refreshProfile();
      await load();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to save the business profile.");
    } finally {
      setProfileSaving(false);
    }
  };

  // ── Scenario modal ──────────────────────────────────────────────
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const [scenarioSaving, setScenarioSaving] = useState(false);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [scenarioForm, setScenarioForm] = useState<ScenarioForm>(EMPTY_SCENARIO);

  const openScenarioModal = (existing?: Scenario) => {
    const assumptions = (existing?.assumptions ?? {}) as Record<string, unknown>;
    const str = (key: string, fallback: string) =>
      assumptions[key] != null ? String(assumptions[key]) : fallback;
    setScenarioForm(
      existing
        ? {
            title: existing.title,
            scenario_type: existing.scenario_type,
            description: existing.description ?? "",
            initial_cost: str("initial_cost", ""),
            expected_monthly_return: str("expected_monthly_return", ""),
            monthly_operating_cost: str("monthly_operating_cost", "0"),
            monthly_growth_pct: str("monthly_growth_pct", "0"),
            horizon_months: str("horizon_months", "12"),
          }
        : EMPTY_SCENARIO
    );
    setScenarioError(null);
    setScenarioOpen(true);
  };

  const submitScenario = async (e: FormEvent) => {
    e.preventDefault();
    setScenarioError(null);
    const assumptions: Record<string, number> = {
      initial_cost: parseFloat(scenarioForm.initial_cost || "0"),
      expected_monthly_return: parseFloat(scenarioForm.expected_monthly_return || "0"),
      monthly_operating_cost: parseFloat(scenarioForm.monthly_operating_cost || "0"),
      monthly_growth_pct: parseFloat(scenarioForm.monthly_growth_pct || "0"),
      horizon_months: parseInt(scenarioForm.horizon_months || "12", 10),
    };
    if (assumptions.initial_cost <= 0) {
      setScenarioError("Upfront cost must be greater than zero so projections are defined.");
      return;
    }
    setScenarioSaving(true);
    try {
      const payload = {
        title: scenarioForm.title.trim(),
        scenario_type: scenarioForm.scenario_type,
        description: scenarioForm.description.trim() || undefined,
        assumptions,
      };
      await businessApi.createScenario(payload);
      setScenarioOpen(false);
      await load();
    } catch (err) {
      setScenarioError(err instanceof Error ? err.message : "Failed to model the scenario.");
    } finally {
      setScenarioSaving(false);
    }
  };

  const deleteScenario = async (id: string) => {
    try {
      await businessApi.deleteScenario(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete the scenario.");
    }
  };

  if (loading) {
    return (
      <div>
        <PageHeader icon={<Building2 className="h-6 w-6" />} title="Business" />
        <LoadingBlock label="Loading business data…" />
      </div>
    );
  }

  // ── Empty state: no business profile ────────────────────────────
  if (!profile) {
    return (
      <div>
        <PageHeader
          icon={<Building2 className="h-6 w-6" />}
          title="Business"
          description="Track business profitability and model what-if scenarios."
        />
        <Card>
          <EmptyState
            icon={<Building2 className="h-6 w-6" />}
            title="No business profile yet"
            description="Create your business profile to unlock profitability tracking, cash-flow analysis and what-if scenarios."
            action={
              <Button onClick={() => openProfileModal(null)}>
                <Plus className="h-4 w-4" /> Create business profile
              </Button>
            }
          />
        </Card>

        <Modal
          open={profileOpen}
          onClose={() => setProfileOpen(false)}
          title="Create business profile"
          footer={
            <>
              <Button variant="secondary" type="button" onClick={() => setProfileOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" form="profile-form" loading={profileSaving}>
                Save profile
              </Button>
            </>
          }
        >
          <ProfileForm
            id="profile-form"
            onSubmit={submitProfile}
            businessName={businessName}
            setBusinessName={setBusinessName}
            businessType={businessType}
            setBusinessType={setBusinessType}
            industry={industry}
            setIndustry={setIndustry}
            availableCapital={availableCapital}
            setAvailableCapital={setAvailableCapital}
            currencyChoice={currencyChoice}
            setCurrencyChoice={setCurrencyChoice}
            description={description}
            setDescription={setDescription}
            error={profileError}
          />
        </Modal>
      </div>
    );
  }

  const currency = summary?.currency ?? profile.currency;
  const currentMonth = summary?.current_month;

  return (
    <div>
      <PageHeader
        icon={<Building2 className="h-6 w-6" />}
        title={profile.business_name}
        description={profile.industry ? `${profile.industry}${profile.business_type ? ` · ${profile.business_type}` : ""}` : profile.business_type || undefined}
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => openProfileModal(profile)}>
              Edit profile
            </Button>
            <Button onClick={() => openScenarioModal()}>
              <Plus className="h-4 w-4" /> New what-if
            </Button>
          </div>
        }
      />

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} onRetry={() => void load()} />
        </div>
      )}

      {summary && currentMonth ? (
        <>
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Revenue (this month)"
              value={formatMoney(currentMonth.revenue, currency)}
              icon={<TrendingUp className="h-5 w-5" />}
              tone="emerald"
            />
            <StatCard
              label="Business expenses"
              value={formatMoney(currentMonth.expenses, currency)}
              tone="red"
            />
            <StatCard
              label="Net profit"
              value={formatMoney(currentMonth.profit, currency)}
              sub={`Margin ${formatPercent(currentMonth.margin_pct)}`}
              tone="indigo"
            />
            <StatCard
              label="Available capital"
              value={formatMoney(summary.available_capital, currency)}
              sub={cashFlow?.runway_months ? `${formatNumber(cashFlow.runway_months)} months runway` : undefined}
              tone="violet"
            />
          </div>

          <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader
                title="Revenue vs business expenses"
                subtitle="Last 6 months · business records only"
              />
              {summary.monthly_trend.length ? (
                <LineChart
                  labels={summary.monthly_trend.map((point) => point.month)}
                  series={[
                    {
                      name: "Revenue",
                      color: "#10b981",
                      data: summary.monthly_trend.map((point) => point.revenue),
                    },
                    {
                      name: "Expenses",
                      color: "#ef4444",
                      data: summary.monthly_trend.map((point) => point.expenses),
                    },
                  ]}
                  formatValue={(value) =>
                    currencySymbol(currency) + Math.round(value).toLocaleString("en-US")
                  }
                />
              ) : (
                <p className="py-12 text-center text-sm text-slate-500">
                  No revenue or business-expense records yet.
                </p>
              )}
            </Card>

            <Card>
              <CardHeader title="Cash flow" subtitle="Average monthly net and runway" />
              {cashFlow && cashFlow.months.length ? (
                <>
                  <BarList
                    items={cashFlow.months.map((month) => ({
                      label: month.month,
                      value: Math.max(0, month.net_cash_flow),
                      color: month.net_cash_flow >= 0 ? "#10b981" : "#ef4444",
                    }))}
                    currencySymbol={currencySymbol(currency)}
                  />
                  <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="rounded-xl bg-slate-900/50 px-2 py-2">
                      <p className="text-[10px] uppercase text-slate-500">Avg net</p>
                      <p className="mt-1 font-semibold text-slate-200">
                        {formatMoney(cashFlow.average_monthly_net, currency)}
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-900/50 px-2 py-2">
                      <p className="text-[10px] uppercase text-slate-500">Positive</p>
                      <p className="mt-1 font-semibold text-emerald-300">{cashFlow.positive_months}</p>
                    </div>
                    <div className="rounded-xl bg-slate-900/50 px-2 py-2">
                      <p className="text-[10px] uppercase text-slate-500">Negative</p>
                      <p className="mt-1 font-semibold text-red-300">{cashFlow.negative_months}</p>
                    </div>
                  </div>
                  <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
                    {cashFlow.revenue_basis} · {cashFlow.expense_basis}
                  </p>
                </>
              ) : (
                <p className="py-12 text-center text-sm text-slate-500">No cash-flow data yet.</p>
              )}
            </Card>
          </div>
        </>
      ) : (
        <Card className="mb-6">
          <p className="text-sm text-slate-400">
            Profile saved. Record income of type <Badge tone="emerald">business_revenue</Badge> and
            expenses in the <Badge tone="violet">Business</Badge> category to see profitability here.
          </p>
        </Card>
      )}

      {/* What-if scenarios */}
      <SectionTitle>What-if scenarios</SectionTitle>
      <p className="mb-4 mt-1 text-xs text-slate-500">
        Projections use only the assumptions you enter — the same inputs always produce the same
        numbers, and no market data is invented.
      </p>

      {scenarios.length ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {scenarios.map((scenario) => {
            const results = scenario.results as ScenarioResult | null;
            return (
              <Card key={scenario.id} hover>
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-bold text-white">{scenario.title}</h3>
                      <Badge tone="sky">{scenario.scenario_type}</Badge>
                    </div>
                    {scenario.description && (
                      <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">
                        {scenario.description}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => void deleteScenario(scenario.id)}
                    className="flex-shrink-0 rounded-lg p-1.5 text-slate-500 hover:bg-red-500/10 hover:text-red-300"
                    aria-label="Delete scenario"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                {results ? (
                  <>
                    <div className="mb-3 grid grid-cols-2 gap-2 text-xs">
                      <div className="rounded-xl bg-slate-900/50 px-3 py-2">
                        <p className="text-[10px] uppercase text-slate-500">Upfront cost</p>
                        <p className="mt-0.5 font-semibold text-slate-200">
                          {formatMoney(results.initial_cost, currency)}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-900/50 px-3 py-2">
                        <p className="text-[10px] uppercase text-slate-500">Horizon</p>
                        <p className="mt-0.5 font-semibold text-slate-200">
                          {results.horizon_months} months
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-900/50 px-3 py-2">
                        <p className="text-[10px] uppercase text-slate-500">Net profit</p>
                        <p
                          className={`mt-0.5 font-semibold ${
                            results.projected_net_profit >= 0 ? "text-emerald-300" : "text-red-300"
                          }`}
                        >
                          {formatMoney(results.projected_net_profit, currency)}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-900/50 px-3 py-2">
                        <p className="text-[10px] uppercase text-slate-500">ROI</p>
                        <p className="mt-0.5 font-semibold text-slate-200">
                          {results.projected_roi_pct != null
                            ? formatPercent(results.projected_roi_pct)
                            : "—"}
                        </p>
                      </div>
                    </div>
                    <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
                      Break-even: {results.break_even_month ? `month ${results.break_even_month}` : "not within horizon"}
                    </p>
                    <ProgressBar
                      value={
                        results.projected_net_profit >= 0 && results.initial_cost > 0
                          ? Math.min(
                              100,
                              (results.projected_net_profit / results.initial_cost) * 50
                            )
                          : 0
                      }
                      tone={results.projected_net_profit >= 0 ? "emerald" : "red"}
                    />
                  </>
                ) : (
                  <p className="text-xs text-slate-500">No projection computed yet.</p>
                )}

                {scenario.ai_analysis && (
                  <div className="mt-4 rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-4 py-3">
                    <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-300">
                      <Sparkles className="h-3 w-3" /> How to read this
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-300">
                      {scenario.ai_analysis}
                    </p>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<TrendingUp className="h-6 w-6" />}
            title="No scenarios yet"
            description="Model an investment, expansion or hiring decision with your own assumptions."
            action={
              <Button size="sm" onClick={() => openScenarioModal()}>
                <Plus className="h-4 w-4" /> New what-if
              </Button>
            }
          />
        </Card>
      )}

      {/* Profile modal */}
      <Modal
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        title="Business profile"
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setProfileOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="profile-form" loading={profileSaving}>
              Save profile
            </Button>
          </>
        }
      >
        <ProfileForm
          id="profile-form"
          onSubmit={submitProfile}
          businessName={businessName}
          setBusinessName={setBusinessName}
          businessType={businessType}
          setBusinessType={setBusinessType}
          industry={industry}
          setIndustry={setIndustry}
          availableCapital={availableCapital}
          setAvailableCapital={setAvailableCapital}
          currencyChoice={currencyChoice}
          setCurrencyChoice={setCurrencyChoice}
          description={description}
          setDescription={setDescription}
          error={profileError}
        />
      </Modal>

      {/* Scenario modal */}
      <Modal
        open={scenarioOpen}
        onClose={() => setScenarioOpen(false)}
        title="Model a what-if scenario"
        subtitle="Every input is yours — the projection is fully deterministic."
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setScenarioOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="scenario-form" loading={scenarioSaving}>
              Model scenario
            </Button>
          </>
        }
      >
        <form id="scenario-form" onSubmit={submitScenario} className="space-y-4">
          <Field label="Scenario title" required>
            <Input
              value={scenarioForm.title}
              onChange={(e) => setScenarioForm({ ...scenarioForm, title: e.target.value })}
              placeholder="e.g. Open second outlet"
              required
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type">
              <Input
                value={scenarioForm.scenario_type}
                onChange={(e) => setScenarioForm({ ...scenarioForm, scenario_type: e.target.value })}
                placeholder="investment / expansion / hiring"
              />
            </Field>
            <Field label="Horizon (months)">
              <Input
                type="number"
                min="1"
                max="120"
                value={scenarioForm.horizon_months}
                onChange={(e) => setScenarioForm({ ...scenarioForm, horizon_months: e.target.value })}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Upfront cost" hint="one-off" required>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={scenarioForm.initial_cost}
                onChange={(e) => setScenarioForm({ ...scenarioForm, initial_cost: e.target.value })}
                required
              />
            </Field>
            <Field label="Expected monthly return" hint="revenue added per month">
              <Input
                type="number"
                min="0"
                step="0.01"
                value={scenarioForm.expected_monthly_return}
                onChange={(e) =>
                  setScenarioForm({ ...scenarioForm, expected_monthly_return: e.target.value })
                }
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Monthly operating cost" hint="recurring">
              <Input
                type="number"
                min="0"
                step="0.01"
                value={scenarioForm.monthly_operating_cost}
                onChange={(e) =>
                  setScenarioForm({ ...scenarioForm, monthly_operating_cost: e.target.value })
                }
              />
            </Field>
            <Field label="Monthly growth %" hint="applied to return">
              <Input
                type="number"
                min="0"
                step="0.1"
                value={scenarioForm.monthly_growth_pct}
                onChange={(e) => setScenarioForm({ ...scenarioForm, monthly_growth_pct: e.target.value })}
              />
            </Field>
          </div>
          <Field label="Description">
            <Textarea
              rows={2}
              value={scenarioForm.description}
              onChange={(e) => setScenarioForm({ ...scenarioForm, description: e.target.value })}
            />
          </Field>
          {scenarioError && <ErrorBanner message={scenarioError} />}
        </form>
      </Modal>
    </div>
  );
}

function ProfileForm({
  id,
  onSubmit,
  businessName,
  setBusinessName,
  businessType,
  setBusinessType,
  industry,
  setIndustry,
  availableCapital,
  setAvailableCapital,
  currencyChoice,
  setCurrencyChoice,
  description,
  setDescription,
  error,
}: {
  id: string;
  onSubmit: (e: FormEvent) => void;
  businessName: string;
  setBusinessName: (v: string) => void;
  businessType: string;
  setBusinessType: (v: string) => void;
  industry: string;
  setIndustry: (v: string) => void;
  availableCapital: string;
  setAvailableCapital: (v: string) => void;
  currencyChoice: string;
  setCurrencyChoice: (v: string) => void;
  description: string;
  setDescription: (v: string) => void;
  error: string | null;
}) {
  return (
    <form id={id} onSubmit={onSubmit} className="space-y-4">
      <Field label="Business name" required>
        <Input
          value={businessName}
          onChange={(e) => setBusinessName(e.target.value)}
          placeholder="e.g. Rafey Electronics"
          required
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Business type">
          <Input
            value={businessType}
            onChange={(e) => setBusinessType(e.target.value)}
            placeholder="Retail / E-commerce"
          />
        </Field>
        <Field label="Industry">
          <Input
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            placeholder="Consumer electronics"
          />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Available capital">
          <Input
            type="number"
            min="0"
            step="0.01"
            value={availableCapital}
            onChange={(e) => setAvailableCapital(e.target.value)}
            placeholder="0.00"
          />
        </Field>
        <Field label="Currency">
          <select
            value={currencyChoice}
            onChange={(e) => setCurrencyChoice(e.target.value)}
            className="w-full rounded-xl border border-slate-700/80 bg-slate-900 px-4 py-2.5 text-sm text-white outline-none focus:border-indigo-500"
          >
            {CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Description">
        <Textarea
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What does the business do?"
        />
      </Field>
      {error && <ErrorBanner message={error} />}
    </form>
  );
}
