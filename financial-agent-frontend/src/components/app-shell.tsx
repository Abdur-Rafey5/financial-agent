"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { cn } from "@/components/ui";
import {
  BarChart3,
  Bot,
  Building2,
  Lightbulb,
  LayoutDashboard,
  LogOut,
  PiggyBank,
  Receipt,
  Settings,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

export const NAV_ITEMS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/transactions", label: "Transactions", icon: Receipt },
  { href: "/dashboard/budgets", label: "Budgets", icon: Wallet },
  { href: "/dashboard/goals", label: "Goals", icon: PiggyBank },
  { href: "/dashboard/reports", label: "Reports", icon: BarChart3 },
  { href: "/dashboard/assistant", label: "AI Assistant", icon: Bot },
  { href: "/dashboard/recommendations", label: "Insights", icon: Lightbulb },
  { href: "/dashboard/investments", label: "Investments", icon: TrendingUp },
  { href: "/dashboard/business", label: "Business", icon: Building2 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

const CATEGORY_COLORS: Record<string, string> = {
  student: "bg-sky-500/10 text-sky-300 border-sky-500/20",
  employee: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  businessman: "bg-violet-500/10 text-violet-300 border-violet-500/20",
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { profile, loading, logout } = useAuth();

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === href : pathname.startsWith(href);

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="glass-panel sticky top-0 hidden h-screen w-64 flex-col rounded-none border-y-0 border-l-0 p-5 lg:flex">
        <Link href="/" className="mb-8 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-500 to-emerald-400 shadow-lg shadow-indigo-500/20">
            <Bot className="h-6 w-6 text-white" />
          </span>
          <span className="text-lg font-bold tracking-tight text-white">
            Fin<span className="text-indigo-400">Agent</span>
          </span>
        </Link>

        <nav className="flex-1 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all",
                  isActive(item.href)
                    ? "bg-indigo-600/20 text-white shadow-inner shadow-indigo-500/10"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100"
                )}
              >
                <Icon className="h-4.5 w-4.5 h-[18px] w-[18px]" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-6 border-t border-slate-800/70 pt-4">
          {loading ? (
            <p className="px-2 text-xs text-slate-500">Loading profile…</p>
          ) : profile ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/40 to-emerald-500/40 text-sm font-bold text-white">
                  {profile.full_name.slice(0, 1).toUpperCase()}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">
                    {profile.full_name}
                  </p>
                  {profile.category && (
                    <span
                      className={cn(
                        "inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize",
                        CATEGORY_COLORS[profile.category] || CATEGORY_COLORS.student
                      )}
                    >
                      {profile.category}
                    </span>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={logout}
                className="flex w-full items-center gap-3 rounded-xl px-3.5 py-2 text-sm font-medium text-slate-400 transition-colors hover:bg-red-500/10 hover:text-red-300"
              >
                <LogOut className="h-4 w-4" /> Sign out
              </button>
            </div>
          ) : (
            <Link href="/login" className="text-sm font-semibold text-indigo-400 hover:text-indigo-300">
              Sign in
            </Link>
          )}
        </div>
      </aside>

      {/* Mobile nav bar */}
      <div className="fixed inset-x-0 top-0 z-40 flex items-center justify-between px-4 py-3 backdrop-blur-md lg:hidden glass-panel rounded-none border-x-0 border-t-0">
        <Link href="/dashboard" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-indigo-500 to-emerald-400">
            <Bot className="h-5 w-5 text-white" />
          </span>
          <span className="font-bold text-white">FinAgent</span>
        </Link>
        <button
          type="button"
          onClick={logout}
          className="rounded-lg p-2 text-slate-400 hover:text-red-300"
          aria-label="Sign out"
        >
          <LogOut className="h-5 w-5" />
        </button>
      </div>
      <nav className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-around overflow-x-auto px-2 py-2 backdrop-blur-md lg:hidden glass-panel rounded-none border-x-0 border-b-0">
        {NAV_ITEMS.slice(0, 6).map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-1 px-2 py-1 text-[10px] font-medium",
                isActive(item.href) ? "text-indigo-300" : "text-slate-400"
              )}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Main content */}
      <main className="relative z-10 min-w-0 flex-1 px-4 pb-24 pt-16 sm:px-6 lg:px-10 lg:pb-10 lg:pt-10">
        {children}
      </main>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div className="flex items-center gap-4">
        {icon && (
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/25 to-emerald-500/10 text-indigo-300">
            {icon}
          </span>
        )}
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">{title}</h1>
          {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
        </div>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}
