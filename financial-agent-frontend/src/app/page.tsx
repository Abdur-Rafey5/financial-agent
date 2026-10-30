"use client";

import Link from "next/link";
import { ArrowRight, Bot, Shield, TrendingUp, Sparkles, PieChart, Users, Building2, GraduationCap } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen flex flex-col justify-between">
      {/* Background ambient decorative glows */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-emerald-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Navigation Header */}
      <header className="w-full max-w-7xl mx-auto px-6 py-6 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <span className="font-bold text-xl tracking-tight text-white">
            Finance<span className="text-indigo-400">Agent</span>
          </span>
        </div>

        <div className="flex items-center gap-4">
          <Link
            href="/login"
            className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="px-5 py-2.5 rounded-lg text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/25 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            Get Started Free
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <main className="w-full max-w-7xl mx-auto px-6 py-16 flex-1 flex flex-col justify-center items-center text-center z-10">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 text-xs font-medium mb-8">
          <Sparkles className="w-3.5 h-3.5" />
          Powered by Google Gemini 1.5 & Live Market Intelligence
        </div>

        <h1 className="text-4xl sm:text-6xl md:text-7xl font-extrabold text-white tracking-tight max-w-4xl leading-[1.1] mb-6">
          Your Autonomous <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-300 to-emerald-400">Financial Co-Pilot</span>
        </h1>

        <p className="text-lg sm:text-xl text-slate-400 max-w-2xl mb-10 leading-relaxed">
          Tailored personal wealth management, automated budgeting, and AI advisory engineered specifically for Students, Working Professionals, and Business Owners.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto mb-16">
          <Link
            href="/register"
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl text-base font-semibold bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 text-white shadow-xl shadow-indigo-600/30 flex items-center justify-center gap-2 transition-all hover:scale-[1.02]"
          >
            Launch Your Agent <ArrowRight className="w-5 h-5" />
          </Link>
          <Link
            href="/login"
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl text-base font-medium glass-panel text-slate-300 hover:text-white hover:bg-slate-800/50 transition-colors"
          >
            Demo Sign In
          </Link>
        </div>

        {/* 3 User Categories Preview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full text-left max-w-5xl">
          {/* Student */}
          <div className="glass-panel glass-panel-hover p-6 rounded-2xl">
            <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-5 text-blue-400">
              <GraduationCap className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Student Dashboard</h3>
            <p className="text-slate-400 text-sm leading-relaxed mb-4">
              Track pocket money, monitor daily safe-spend burn rate, and build lifelong savings habits without going broke.
            </p>
            <div className="text-xs text-blue-400 font-medium">Daily allowance tracking & micro-savings &rarr;</div>
          </div>

          {/* Employee */}
          <div className="glass-panel glass-panel-hover p-6 rounded-2xl">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-5 text-emerald-400">
              <Users className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Employee Wealth</h3>
            <p className="text-slate-400 text-sm leading-relaxed mb-4">
              Automated 50/30/20 budget allocations, salary expense categorization, and milestone goal contribution tracking.
            </p>
            <div className="text-xs text-emerald-400 font-medium">Salary budgeting & goal milestone audit &rarr;</div>
          </div>

          {/* Businessman */}
          <div className="glass-panel glass-panel-hover p-6 rounded-2xl">
            <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-5 text-purple-400">
              <Building2 className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Business & Scenarios</h3>
            <p className="text-slate-400 text-sm leading-relaxed mb-4">
              Management financial overview, gross margins, cash flow runway, and AI what-if scenario simulations.
            </p>
            <div className="text-xs text-purple-400 font-medium">Cash flow runway & ROI modeling &rarr;</div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-slate-800/80 py-6 text-center text-xs text-slate-500">
        © 2026 AI-Powered Financial Agent. Built with FastAPI, PostgreSQL, and Google Gemini.
      </footer>
    </div>
  );
}
