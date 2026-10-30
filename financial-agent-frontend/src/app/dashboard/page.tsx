"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bot,
  TrendingUp,
  TrendingDown,
  Wallet,
  PiggyBank,
  Target,
  Sparkles,
  Send,
  Plus,
  BarChart3,
  LogOut,
  GraduationCap,
  Users,
  Building2,
  DollarSign,
  ArrowUpRight,
  ShieldAlert,
} from "lucide-react";
import { apiFetch, clearStoredToken } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "assistant" | "investments" | "business">("overview");

  // AI Assistant chat state
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; content: string }>>([
    {
      role: "assistant",
      content: "Hello! I am your AI Financial Advisor. Ask me anything about your current budget, safe spending limits, or investments.",
    },
  ]);
  const [chatLoading, setChatLoading] = useState(false);

  // New Transaction Modal State
  const [showTransactionModal, setShowTransactionModal] = useState(false);
  const [txType, setTxType] = useState<"income" | "expense">("expense");
  const [txAmount, setTxAmount] = useState("");
  const [txSource, setTxSource] = useState("");
  const [txDate, setTxDate] = useState("");

  // Market Watchlist State
  const [watchlist, setWatchlist] = useState<any[]>([]);

  useEffect(() => {
    setTxDate(new Date().toISOString().split("T")[0]);
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const userProfile = await apiFetch<any>("/users/me");
      if (!userProfile.onboarding_completed) {
        router.push("/onboarding");
        return;
      }
      setProfile(userProfile);

      const dashSummary = await apiFetch<any>("/dashboard/summary");
      setSummary(dashSummary);

      // Load investments watchlist
      const stocks = await apiFetch<any[]>("/investments/watchlist");
      setWatchlist(stocks);
    } catch (err: any) {
      console.error(err);
      clearStoredToken();
      router.push("/login");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    clearStoredToken();
    router.push("/login");
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userText = chatInput;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: userText }]);
    setChatLoading(true);

    try {
      const res = await apiFetch<any>("/assistant/chat", {
        method: "POST",
        body: JSON.stringify({ message: userText }),
      });
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.message.content },
      ]);
    } catch (err: any) {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error contacting advisor. Please retry." },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleCreateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const endpoint = txType === "income" ? "/income" : "/expenses";
      const payload: any = {
        amount: parseFloat(txAmount),
        currency: "PKR",
        date: txDate,
      };
      if (txType === "income") {
        payload.source = txSource;
        payload.income_type = "allowance_salary";
      } else {
        payload.description = txSource;
      }

      await apiFetch(endpoint, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setShowTransactionModal(false);
      setTxAmount("");
      setTxSource("");
      loadDashboardData();
    } catch (err: any) {
      alert(err.message || "Failed to record transaction.");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-indigo-600/20 flex items-center justify-center animate-spin">
            <Bot className="w-6 h-6 text-indigo-400" />
          </div>
          <span className="text-sm text-slate-400">Loading your financial dashboard...</span>
        </div>
      </div>
    );
  }

  const category = profile?.category || "student";

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Navigation */}
      <header className="border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-emerald-400 flex items-center justify-center shadow-md shadow-indigo-500/20">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-lg text-white">
                Finance<span className="text-indigo-400">Agent</span>
              </span>
            </div>

            {/* Category Badge */}
            <div className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
              {category === "student" && <GraduationCap className="w-3.5 h-3.5 text-blue-400" />}
              {category === "employee" && <Users className="w-3.5 h-3.5 text-emerald-400" />}
              {category === "businessman" && <Building2 className="w-3.5 h-3.5 text-purple-400" />}
              <span>{category} Mode</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowTransactionModal(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 transition-all"
            >
              <Plus className="w-4 h-4" /> Add Record
            </button>
            <button
              onClick={handleLogout}
              className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex-1 w-full space-y-8">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "overview"
                ? "bg-slate-800 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Financial Overview
          </button>
          <button
            onClick={() => setActiveTab("assistant")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all inline-flex items-center gap-1.5 ${
              activeTab === "assistant"
                ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Sparkles className="w-4 h-4 text-indigo-400" /> AI Advisor
          </button>
          <button
            onClick={() => setActiveTab("investments")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "investments"
                ? "bg-slate-800 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            US Stocks Watchlist
          </button>
        </div>

        {/* Tab 1: Overview */}
        {activeTab === "overview" && (
          <div className="space-y-8">
            {/* Top Stat Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="glass-panel p-5 rounded-2xl">
                <div className="flex items-center justify-between text-slate-400 mb-2">
                  <span className="text-xs font-semibold uppercase tracking-wider">This Month Income</span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-white">
                  PKR {summary?.total_income_this_month?.toLocaleString() || "0"}
                </div>
              </div>

              <div className="glass-panel p-5 rounded-2xl">
                <div className="flex items-center justify-between text-slate-400 mb-2">
                  <span className="text-xs font-semibold uppercase tracking-wider">This Month Expenses</span>
                  <div className="w-8 h-8 rounded-lg bg-rose-500/10 flex items-center justify-center text-rose-400">
                    <TrendingDown className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-white">
                  PKR {summary?.total_expenses_this_month?.toLocaleString() || "0"}
                </div>
              </div>

              <div className="glass-panel p-5 rounded-2xl">
                <div className="flex items-center justify-between text-slate-400 mb-2">
                  <span className="text-xs font-semibold uppercase tracking-wider">Net Savings</span>
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                    <PiggyBank className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-white">
                  PKR {summary?.net_savings_this_month?.toLocaleString() || "0"}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Savings Rate: <span className="text-emerald-400 font-semibold">{summary?.savings_rate_pct || 0}%</span>
                </div>
              </div>

              {/* Dynamic Category Specific Stat */}
              <div className="glass-panel p-5 rounded-2xl border-indigo-500/20 bg-indigo-950/10">
                <div className="flex items-center justify-between text-indigo-300 mb-2">
                  <span className="text-xs font-semibold uppercase tracking-wider">
                    {category === "student" && "Safe Daily Spend"}
                    {category === "employee" && "20% Savings Target"}
                    {category === "businessman" && "Gross Margin"}
                  </span>
                  <Sparkles className="w-4 h-4 text-indigo-400" />
                </div>
                <div className="text-2xl font-bold text-white">
                  {category === "student" && `PKR ${summary?.category_metrics?.safe_daily_budget || 0}`}
                  {category === "employee" && `PKR ${summary?.category_metrics?.recommended_savings_goal?.toLocaleString() || 0}`}
                  {category === "businessman" && `${summary?.category_metrics?.gross_margin_pct || 0}%`}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  {category === "student" && `${summary?.category_metrics?.days_remaining_in_month || 0} days left this cycle`}
                  {category === "employee" && (summary?.category_metrics?.savings_goal_met ? "✅ On track this month" : "⚠️ Needs contribution")}
                  {category === "businessman" && `Operating runway positive`}
                </div>
              </div>
            </div>

            {/* Transactions & Financial Breakdown */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Recent Activity */}
              <div className="lg:col-span-2 glass-panel p-6 rounded-2xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-base text-white">Recent Transactions</h3>
                  <button
                    onClick={() => setShowTransactionModal(true)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                  >
                    + Add New
                  </button>
                </div>

                {summary?.recent_transactions?.length === 0 ? (
                  <div className="text-center py-10 text-slate-500 text-sm">
                    No transactions entered yet. Click &apos;Add Record&apos; to log your first income or expense.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-800">
                    {summary?.recent_transactions?.map((tx: any) => (
                      <div key={tx.id} className="py-3.5 flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium text-white">{tx.source}</div>
                          <div className="text-xs text-slate-500">{tx.date}</div>
                        </div>
                        <div
                          className={`text-sm font-semibold ${
                            tx.type === "income" ? "text-emerald-400" : "text-slate-200"
                          }`}
                        >
                          {tx.type === "income" ? "+" : "-"} PKR {tx.amount.toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Quick AI Proactive Insight */}
              <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 text-indigo-400 mb-3 text-xs font-semibold uppercase tracking-wider">
                    <Sparkles className="w-4 h-4" /> Agent Proactive Insight
                  </div>
                  <h4 className="text-base font-bold text-white mb-2">
                    {category === "student" && "Daily Burn Budget Active"}
                    {category === "employee" && "Automated Wealth Blueprint"}
                    {category === "businessman" && "Cash Flow Resilience"}
                  </h4>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {category === "student" &&
                      "Based on your pocket money balance, keeping daily spending below your safe threshold will protect your emergency cushion until month-end."}
                    {category === "employee" &&
                      "You have maintained consistent discipline. Consider directing any surplus above your 50/30/20 target into high-yield stocks or savings goals."}
                    {category === "businessman" &&
                      "Monitor receivables regularly. Maintain 3-6 months operating expenses in liquid accounts before expanding inventory."}
                  </p>
                </div>

                <button
                  onClick={() => setActiveTab("assistant")}
                  className="mt-6 w-full py-2.5 rounded-xl text-xs font-semibold bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 transition-all"
                >
                  Ask Advisor More &rarr;
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: AI Advisor Chat */}
        {activeTab === "assistant" && (
          <div className="glass-panel rounded-2xl flex flex-col h-[650px] overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/40">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-indigo-600/20 flex items-center justify-center text-indigo-400">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Gemini Financial Advisor</h3>
                  <p className="text-xs text-slate-400">Domain-tailored for {category}</p>
                </div>
              </div>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 p-6 overflow-y-auto space-y-4">
              {chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-xl rounded-2xl px-5 py-3.5 text-sm leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-indigo-600 text-white"
                        : "glass-panel border-slate-700/80 text-slate-200"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="glass-panel rounded-2xl px-5 py-3.5 text-sm text-slate-400 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 animate-spin text-indigo-400" />
                    Analyzing financial context...
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <form onSubmit={handleSendMessage} className="p-4 border-t border-slate-800 bg-slate-900/40 flex items-center gap-3">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask about budget adjustments, savings strategies, or scenario planning..."
                className="flex-1 px-4 py-3 rounded-xl bg-slate-950 border border-slate-700 text-white text-sm outline-none focus:border-indigo-500"
              />
              <button
                type="submit"
                disabled={chatLoading || !chatInput.trim()}
                className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 transition-all"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        )}

        {/* Tab 3: Investments & Watchlist */}
        {activeTab === "investments" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-white">US Stock Market Watchlist</h3>
                <p className="text-xs text-slate-400">Real-time / simulated quotes via Alpha Vantage adapter (USD)</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {watchlist.map((stock) => (
                <div key={stock.symbol} className="glass-panel p-5 rounded-2xl">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-bold text-base text-white">{stock.symbol}</span>
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded ${
                        stock.change >= 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                      }`}
                    >
                      {stock.change_percent}
                    </span>
                  </div>
                  <div className="text-2xl font-extrabold text-white mb-2">
                    ${stock.price.toFixed(2)}
                  </div>
                  <div className="text-xs text-slate-400 flex items-center justify-between">
                    <span>High: ${stock.high}</span>
                    <span>Low: ${stock.low}</span>
                  </div>
                  <div className="mt-3 pt-3 border-t border-slate-800 text-[10px] text-slate-500">
                    Source: {stock.source}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Add Record Modal */}
      {showTransactionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel p-6 rounded-2xl">
            <h3 className="text-lg font-bold text-white mb-4">Add Financial Record</h3>
            <form onSubmit={handleCreateTransaction} className="space-y-4">
              <div className="grid grid-cols-2 gap-2 p-1 bg-slate-900 rounded-xl border border-slate-800">
                <button
                  type="button"
                  onClick={() => setTxType("expense")}
                  className={`py-2 text-xs font-semibold rounded-lg transition-all ${
                    txType === "expense" ? "bg-rose-600 text-white" : "text-slate-400"
                  }`}
                >
                  Expense
                </button>
                <button
                  type="button"
                  onClick={() => setTxType("income")}
                  className={`py-2 text-xs font-semibold rounded-lg transition-all ${
                    txType === "income" ? "bg-emerald-600 text-white" : "text-slate-400"
                  }`}
                >
                  Income
                </button>
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">Amount (PKR)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={txAmount}
                  onChange={(e) => setTxAmount(e.target.value)}
                  placeholder="e.g. 2500"
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  {txType === "income" ? "Income Source" : "Expense Description"}
                </label>
                <input
                  type="text"
                  required
                  value={txSource}
                  onChange={(e) => setTxSource(e.target.value)}
                  placeholder={txType === "income" ? "Salary, Pocket Money, Freelance" : "Groceries, Books, Cloud Server"}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">Date</label>
                <input
                  type="date"
                  required
                  value={txDate}
                  onChange={(e) => setTxDate(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-sm outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowTransactionModal(false)}
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
                >
                  Save Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
