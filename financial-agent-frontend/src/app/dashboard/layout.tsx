"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import { getStoredToken } from "@/lib/api";
import { AppShell } from "@/components/app-shell";
import { Loader2 } from "lucide-react";

/**
 * Route guard: only authenticated users reach the dashboard shell.
 */
function Guard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { profile, loading } = useAuth();

  useEffect(() => {
    if (!loading && !profile && !getStoredToken()) {
      router.replace("/login");
    }
  }, [loading, profile, router]);

  if (loading || !profile) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-sm text-slate-400">
        <Loader2 className="h-7 w-7 animate-spin text-indigo-400" />
        Preparing your dashboard…
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <Guard>{children}</Guard>
    </AuthProvider>
  );
}
