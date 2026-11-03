"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { GraduationCap, Users, Building2, Check, ArrowRight, Sparkles } from "lucide-react";
import { businessApi, usersApi } from "@/lib/api";
import type { Category } from "@/lib/types";

type CategoryType = Category;

export default function OnboardingPage() {
  const router = useRouter();
  const [selectedCategory, setSelectedCategory] = useState<CategoryType>("student");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Category specific fields
  const [allowanceAmount, setAllowanceAmount] = useState("15000");
  const [allowanceFrequency, setAllowanceFrequency] = useState("monthly");
  const [monthlySalary, setMonthlySalary] = useState("120000");
  const [employerName, setEmployerName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] = useState("Retail / E-commerce");
  const [availableCapital, setAvailableCapital] = useState("500000");

  const handleComplete = async () => {
    setLoading(true);
    setError(null);

    try {
      const payload: {
        category: Category;
        currency: string;
        allowance_amount?: number;
        allowance_frequency?: string;
        monthly_salary?: number;
        employer_name?: string;
      } = {
        category: selectedCategory,
        currency: "PKR",
      };

      if (selectedCategory === "student") {
        payload.allowance_amount = parseFloat(allowanceAmount) || 0;
        payload.allowance_frequency = allowanceFrequency;
      } else if (selectedCategory === "employee") {
        payload.monthly_salary = parseFloat(monthlySalary) || 0;
        payload.employer_name = employerName;
      }

      await usersApi.onboarding(payload);

      // If businessman, also register business profile
      if (selectedCategory === "businessman" && businessName) {
        await businessApi.upsertProfile({
          business_name: businessName,
          business_type: businessType,
          available_capital: parseFloat(availableCapital) || 0,
          currency: "PKR",
        });
      }

      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete onboarding.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen py-16 px-4 flex flex-col items-center justify-center relative">
      <div className="w-full max-w-3xl glass-panel p-8 sm:p-10 rounded-3xl relative z-10">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            Step 1 of 1: Personalization
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Select Your Financial Track</h1>
          <p className="text-sm sm:text-base text-slate-400 mt-2 max-w-lg mx-auto">
            Choose the mode that best describes your current financial stage. You can change this anytime.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
            {error}
          </div>
        )}

        {/* Category Choice Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {/* Student Card */}
          <div
            onClick={() => setSelectedCategory("student")}
            className={`cursor-pointer rounded-2xl p-5 border transition-all text-left relative ${
              selectedCategory === "student"
                ? "bg-indigo-600/15 border-indigo-500 shadow-lg shadow-indigo-500/20"
                : "glass-panel border-slate-700/60 hover:border-slate-500/60 opacity-80"
            }`}
          >
            {selectedCategory === "student" && (
              <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-indigo-500 flex items-center justify-center text-white">
                <Check className="w-3.5 h-3.5" />
              </div>
            )}
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400 mb-4">
              <GraduationCap className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-white text-base mb-1">Student</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Pocket money budgeting, daily safe spend limits, and savings goals.
            </p>
          </div>

          {/* Employee Card */}
          <div
            onClick={() => setSelectedCategory("employee")}
            className={`cursor-pointer rounded-2xl p-5 border transition-all text-left relative ${
              selectedCategory === "employee"
                ? "bg-emerald-600/15 border-emerald-500 shadow-lg shadow-emerald-500/20"
                : "glass-panel border-slate-700/60 hover:border-slate-500/60 opacity-80"
            }`}
          >
            {selectedCategory === "employee" && (
              <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center text-white">
                <Check className="w-3.5 h-3.5" />
              </div>
            )}
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-400 mb-4">
              <Users className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-white text-base mb-1">Employee</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Salary allocations, monthly expense categories, and 50/30/20 wealth rules.
            </p>
          </div>

          {/* Businessman Card */}
          <div
            onClick={() => setSelectedCategory("businessman")}
            className={`cursor-pointer rounded-2xl p-5 border transition-all text-left relative ${
              selectedCategory === "businessman"
                ? "bg-purple-600/15 border-purple-500 shadow-lg shadow-purple-500/20"
                : "glass-panel border-slate-700/60 hover:border-slate-500/60 opacity-80"
            }`}
          >
            {selectedCategory === "businessman" && (
              <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-purple-500 flex items-center justify-center text-white">
                <Check className="w-3.5 h-3.5" />
              </div>
            )}
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-400 mb-4">
              <Building2 className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-white text-base mb-1">Businessman</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Business cash flow, gross margins, capital tracking, and what-if scenarios.
            </p>
          </div>
        </div>

        {/* Dynamic Category Profile Fields */}
        <div className="glass-panel p-6 rounded-2xl mb-8 space-y-4">
          <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-2">
            Configure {selectedCategory.toUpperCase()} Profile
          </h4>

          {selectedCategory === "student" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-300 font-medium mb-1">Pocket Money / Allowance (PKR)</label>
                <input
                  type="number"
                  value={allowanceAmount}
                  onChange={(e) => setAllowanceAmount(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-300 font-medium mb-1">Frequency</label>
                <select
                  value={allowanceFrequency}
                  onChange={(e) => setAllowanceFrequency(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-indigo-500"
                >
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
            </div>
          )}

          {selectedCategory === "employee" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-300 font-medium mb-1">Monthly Net Salary (PKR)</label>
                <input
                  type="number"
                  value={monthlySalary}
                  onChange={(e) => setMonthlySalary(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-300 font-medium mb-1">Employer / Company Name (Optional)</label>
                <input
                  type="text"
                  value={employerName}
                  onChange={(e) => setEmployerName(e.target.value)}
                  placeholder="e.g. Acme Tech"
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-emerald-500"
                />
              </div>
            </div>
          )}

          {selectedCategory === "businessman" && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-slate-300 font-medium mb-1">Business Name</label>
                <input
                  type="text"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  placeholder="e.g. Crescent Trading"
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-purple-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-300 font-medium mb-1">Industry / Type</label>
                <input
                  type="text"
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                  placeholder="Retail / Logistics"
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-purple-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-300 font-medium mb-1">Operating Capital (PKR)</label>
                <input
                  type="number"
                  value={availableCapital}
                  onChange={(e) => setAvailableCapital(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-purple-500"
                />
              </div>
            </div>
          )}
        </div>

        <button
          onClick={handleComplete}
          disabled={loading}
          className="w-full py-4 rounded-xl font-bold bg-gradient-to-r from-indigo-500 via-purple-600 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 text-white shadow-xl shadow-indigo-600/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
        >
          {loading ? "Personalizing Agent..." : "Launch My Dashboard"} <ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
