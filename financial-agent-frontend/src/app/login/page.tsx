"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowRight, Bot, Lock, Mail, Play } from "lucide-react";
import { authApi, setStoredToken, setStoredUser } from "@/lib/api";
import type { AuthResponse } from "@/lib/types";
import { Button, Card, Field, Input } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  const routeAfterAuth = (res: AuthResponse) => {
    setStoredToken(res.access_token);
    setStoredUser(res.user);
    router.push(res.user.has_profile ? "/dashboard" : "/onboarding");
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.login({ email, password });
      routeAfterAuth(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign in. Please verify your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setError(null);
    setDemoLoading(true);
    try {
      const res = await authApi.demo();
      routeAfterAuth(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the demo. Please try again.");
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4">
      <div className="pointer-events-none absolute -top-32 left-1/3 h-80 w-80 rounded-full bg-indigo-600/20 blur-3xl" />

      <Card className="relative z-10 w-full max-w-md p-8">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-500 to-emerald-400 shadow-lg shadow-indigo-500/20">
            <Bot className="h-7 w-7 text-white" />
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-white">Welcome back</h1>
          <p className="mt-1 text-sm text-slate-400">Sign in to your FinAgent account</p>
        </div>

        {error && (
          <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Email address">
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
              <Input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="pl-11"
              />
            </div>
          </Field>

          <Field label="Password">
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
              <Input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="pl-11"
              />
            </div>
          </Field>

          <Button type="submit" size="lg" loading={loading} className="mt-2 w-full">
            {!loading && <ArrowRight className="h-4 w-4" />}
            Sign in
          </Button>
        </form>

        <Button
          type="button"
          variant="secondary"
          size="lg"
          onClick={handleDemo}
          loading={demoLoading}
          className="mt-3 w-full"
        >
          {!demoLoading && <Play className="h-4 w-4" />}
          Use demo account
        </Button>

        <p className="mt-8 text-center text-sm text-slate-400">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-semibold text-indigo-400 hover:text-indigo-300">
            Create an account
          </Link>
        </p>
      </Card>
    </div>
  );
}
