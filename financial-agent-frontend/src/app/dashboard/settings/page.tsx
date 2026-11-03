"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Building2, GraduationCap, Save, Settings, Users } from "lucide-react";
import { usersApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Category } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorBanner,
  Field,
  Input,
  Modal,
  Select,
} from "@/components/ui";
import { PageHeader } from "@/components/app-shell";

const CATEGORIES: { value: Category; label: string; icon: typeof Users; description: string }[] = [
  {
    value: "student",
    label: "Student",
    icon: GraduationCap,
    description: "Allowance-based tracking with safe daily spend",
  },
  {
    value: "employee",
    label: "Employee",
    icon: Users,
    description: "Salary planning with budgets and savings goals",
  },
  {
    value: "businessman",
    label: "Businessman",
    icon: Building2,
    description: "Revenue, profitability and what-if scenarios",
  },
];

const CURRENCIES = ["PKR", "USD", "EUR", "GBP", "INR", "AED", "SAR"];
const FREQUENCIES = ["weekly", "biweekly", "monthly", "quarterly", "yearly"];

export default function SettingsPage() {
  const { profile, refreshProfile } = useAuth();

  const [fullName, setFullName] = useState("");
  const [category, setCategory] = useState<Category | "">("");
  const [currency, setCurrency] = useState("PKR");
  const [allowanceAmount, setAllowanceAmount] = useState("");
  const [allowanceFrequency, setAllowanceFrequency] = useState("monthly");
  const [monthlySalary, setMonthlySalary] = useState("");
  const [employerName, setEmployerName] = useState("");

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [categoryOpen, setCategoryOpen] = useState(false);
  const [categorySaving, setCategorySaving] = useState(false);
  const [categoryError, setCategoryError] = useState<string | null>(null);
  const [pendingCategory, setPendingCategory] = useState<Category | null>(null);

  useEffect(() => {
    if (!profile) return;
    setFullName(profile.full_name);
    setCategory((profile.category as Category) ?? "");
    setCurrency(profile.currency);
    setAllowanceAmount(profile.allowance_amount != null ? String(profile.allowance_amount) : "");
    setAllowanceFrequency(profile.allowance_frequency ?? "monthly");
    setMonthlySalary(profile.monthly_salary != null ? String(profile.monthly_salary) : "");
    setEmployerName(profile.employer_name ?? "");
  }, [profile]);

  const isBusinessman = category === "businessman";
  const studentFieldsActive = category === "student";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        full_name: fullName.trim(),
        currency,
      };
      if (category) payload.category = category;
      if (studentFieldsActive) {
        if (allowanceAmount !== "") payload.allowance_amount = parseFloat(allowanceAmount);
        payload.allowance_frequency = allowanceFrequency;
      } else {
        payload.allowance_amount = null;
        payload.allowance_frequency = null;
      }
      if (category === "employee" || isBusinessman) {
        if (monthlySalary !== "") payload.monthly_salary = parseFloat(monthlySalary);
        payload.employer_name = employerName.trim() || null;
      } else {
        payload.monthly_salary = null;
        payload.employer_name = null;
      }

      await usersApi.updateMe(payload);
      await refreshProfile();
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  };

  const requestCategoryChange = (next: Category) => {
    if (next === category) return;
    setPendingCategory(next);
    setCategoryError(null);
    setCategoryOpen(true);
  };

  const confirmCategoryChange = async () => {
    if (!pendingCategory) return;
    setCategorySaving(true);
    setCategoryError(null);
    try {
      await usersApi.updateMe({ category: pendingCategory });
      await refreshProfile();
      setCategory(pendingCategory);
      setCategoryOpen(false);
      setSaved(true);
    } catch (err) {
      setCategoryError(err instanceof Error ? err.message : "Failed to change your track.");
    } finally {
      setCategorySaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        icon={<Settings className="h-6 w-6" />}
        title="Settings"
        description="Your profile, currency and track-specific income details."
      />

      {saved && (
        <div className="mb-5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          Settings saved.
        </div>
      )}
      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} />
        </div>
      )}

      {!profile?.onboarding_completed && (
        <div className="mb-5 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          Your onboarding was not completed — save a track and currency below to finish it.
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Account" subtitle="Signed in as a real authenticated user" />
          <form onSubmit={submit} className="space-y-4">
            <Field label="Full name" required>
              <Input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </Field>
            <Field label="Email" hint="managed by authentication">
              <Input value={profile?.email ?? ""} disabled className="opacity-60" />
            </Field>

            <Field label="Track" hint="changing opens a confirmation">
              <div className="grid grid-cols-3 gap-2">
                {CATEGORIES.map((track) => {
                  const Icon = track.icon;
                  const selected = category === track.value;
                  return (
                    <button
                      key={track.value}
                      type="button"
                      onClick={() => requestCategoryChange(track.value)}
                      className={`rounded-xl border p-3 text-left transition-all ${
                        selected
                          ? "border-indigo-500/60 bg-indigo-500/10"
                          : "border-slate-700/70 hover:border-slate-500"
                      }`}
                    >
                      <Icon className={`h-5 w-5 ${selected ? "text-indigo-300" : "text-slate-500"}`} />
                      <p className="mt-2 text-xs font-semibold text-white">{track.label}</p>
                    </button>
                  );
                })}
              </div>
            </Field>

            <Field label="Currency" required>
              <Select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {CURRENCIES.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </Select>
            </Field>

            {/* Track-specific fields */}
            {studentFieldsActive && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Allowance amount">
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={allowanceAmount}
                    onChange={(e) => setAllowanceAmount(e.target.value)}
                    placeholder="15000"
                  />
                </Field>
                <Field label="Frequency">
                  <Select
                    value={allowanceFrequency}
                    onChange={(e) => setAllowanceFrequency(e.target.value)}
                  >
                    {FREQUENCIES.map((frequency) => (
                      <option key={frequency} value={frequency}>
                        {frequency}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            )}
            {(category === "employee" || isBusinessman) && !studentFieldsActive && (
              <>
                <Field label="Monthly salary" hint={isBusinessman ? "fixed draw/transfers" : "optional"}>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={monthlySalary}
                    onChange={(e) => setMonthlySalary(e.target.value)}
                    placeholder="120000"
                  />
                </Field>
                <Field label="Employer name">
                  <Input
                    value={employerName}
                    onChange={(e) => setEmployerName(e.target.value)}
                    placeholder="Company Ltd"
                  />
                </Field>
              </>
            )}

            <Button type="submit" loading={saving}>
              <Save className="h-4 w-4" /> Save settings
            </Button>
          </form>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Track details" subtitle="What each track unlocks" />
            <div className="space-y-4">
              {CATEGORIES.map((track) => {
                const Icon = track.icon;
                return (
                  <div key={track.value} className="flex items-start gap-3">
                    <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-slate-800/70">
                      <Icon className="h-4.5 w-4.5 h-[18px] w-[18px] text-slate-300" />
                    </span>
                    <div>
                      <p className="flex items-center gap-2 text-sm font-semibold text-white">
                        {track.label}
                        {category === track.value && <Badge tone="indigo">current</Badge>}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-500">{track.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card>
            <CardHeader title="Demo access" />
            <p className="text-xs leading-relaxed text-slate-400">
              A seeded demo account is available on the login screen when the backend runs with{" "}
              <code className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px]">SEED_DEMO_DATA=true</code>.
              It ships with sample income, expenses, budgets and goals so every surface can be
              explored without setup.
            </p>
          </Card>
        </div>
      </div>

      {/* Category-change confirmation */}
      <Modal
        open={categoryOpen}
        onClose={() => setCategoryOpen(false)}
        title="Change your track?"
        subtitle={`Switching from ${category || "—"} to ${pendingCategory ?? "—"}`}
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setCategoryOpen(false)}>
              Cancel
            </Button>
            <Button loading={categorySaving} onClick={() => void confirmCategoryChange()}>
              Switch track
            </Button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-slate-300">
          Your recorded transactions, budgets and goals stay exactly as they are — the track only
          changes which dashboard insights and income fields are emphasised.
        </p>
        {categoryError && (
          <div className="mt-4">
            <ErrorBanner message={categoryError} />
          </div>
        )}
      </Modal>
    </div>
  );
}
