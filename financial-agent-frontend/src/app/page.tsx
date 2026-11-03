"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Bot,
  Building2,
  GraduationCap,
  LineChart,
  Play,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  Wallet,
} from "lucide-react";
import { authApi, setStoredToken, setStoredUser } from "@/lib/api";
import { Badge, Button, Card } from "@/components/ui";

const TRACKS = [
  {
    icon: GraduationCap,
    accent: "text-sky-300",
    ring: "border-sky-500/30 bg-sky-500/10",
    title: "Students",
    description:
      "Track your allowance and see a safe daily spend so your money lasts the whole month instead of the first week.",
    points: ["Allowance tracking", "Safe daily spend", "Micro-savings goals"],
  },
  {
    icon: Users,
    accent: "text-emerald-300",
    ring: "border-emerald-500/30 bg-emerald-500/10",
    title: "Employees",
    description:
      "Turn your salary into a plan with savings targets and category budgets that adapt to how you actually spend.",
    points: ["Salary planning", "Savings targets", "Category budgets"],
  },
  {
    icon: Building2,
    accent: "text-violet-300",
    ring: "border-violet-500/30 bg-violet-500/10",
    title: "Businessmen",
    description:
      "Understand profitability, watch your cash flow, and model what-if scenarios before you commit real capital.",
    points: ["Profitability", "Cash flow", "What-if scenarios"],
  },
] as const;

export default function LandingPage() {
  const router = useRouter();
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoCredentials, setDemoCredentials] = useState<{ email: string; password: string } | null>(
    null
  );

  useEffect(() => {
    let active = true;
    authApi
      .demoCredentials()
      .then((creds) => {
        if (active) setDemoCredentials(creds);
      })
      .catch(() => {
        /* demo credentials are optional; ignore failures */
      });
    return () => {
      active = false;
    };
  }, []);

  const handleDemo = async () => {
    setError(null);
    setDemoLoading(true);
    try {
      const res = await authApi.demo();
      setStoredToken(res.access_token);
      setStoredUser(res.user);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not start the demo. Please try again."
      );
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex flex-col overflow-hidden">
      {/* Ambient background glows */}
      <div className="pointer-events-none absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
      <div className="pointer-events-none absolute top-1/3 -right-32 h-96 w-96 rounded-full bg-emerald-600/10 blur-3xl" />

      {/* Nav */}
      <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-500 to-emerald-400 shadow-lg shadow-indigo-500/20">
            <Bot className="h-6 w-6 text-white" />
          </span>
          <span className="text-xl font-bold tracking-tight text-white">
            Fin<span className="text-indigo-400">Agent</span>
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="rounded-xl px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:text-white"
          >
            Sign in
          </Link>
          <Link href="/register">
            <Button size="md">Get started</Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <main className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col px-6">
        <section className="flex flex-col items-center py-16 text-center">
          <Badge tone="indigo" className="mb-6 gap-2 px-3.5 py-1.5 text-xs">
            <Sparkles className="h-3.5 w-3.5" />
            AI-powered, grounded in your real numbers
          </Badge>

          <h1 className="max-w-4xl text-4xl font-extrabold leading-[1.1] tracking-tight text-white sm:text-6xl">
            AI-powered financial management for{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-violet-300 to-emerald-400 bg-clip-text text-transparent">
              students, employees &amp; businessmen
            </span>
          </h1>

          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-slate-400">
            FinAgent helps you budget, save and grow with an assistant that explains the numbers —
            it shows what is a fact from your data and what is an estimate, so you always know what
            you are looking at.
          </p>

          <div className="mt-10 flex w-full flex-col items-center gap-4 sm:w-auto sm:flex-row">
            <Link href="/register" className="w-full sm:w-auto">
              <Button size="lg" className="w-full sm:w-auto">
                Create your account <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login" className="w-full sm:w-auto">
              <Button size="lg" variant="secondary" className="w-full sm:w-auto">
                Sign in
              </Button>
            </Link>
            <Button
              size="lg"
              variant="ghost"
              className="w-full sm:w-auto"
              onClick={handleDemo}
              loading={demoLoading}
            >
              {!demoLoading && <Play className="h-4 w-4" />}
              Try the demo
            </Button>
          </div>

          {demoCredentials && (
            <p className="mt-4 text-xs text-slate-500">
              Demo account:{" "}
              <span className="font-medium text-slate-300">{demoCredentials.email}</span> ·{" "}
              <span className="font-medium text-slate-300">{demoCredentials.password}</span>
            </p>
          )}

          {error && (
            <p className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-2 text-sm text-red-300">
              {error}
            </p>
          )}
        </section>

        {/* Feature grid */}
        <section className="grid grid-cols-1 gap-6 py-10 md:grid-cols-3">
          {TRACKS.map((track) => (
            <Card key={track.title} hover className="flex flex-col">
              <span
                className={`mb-5 flex h-12 w-12 items-center justify-center rounded-xl border ${track.ring} ${track.accent}`}
              >
                <track.icon className="h-6 w-6" />
              </span>
              <h3 className="mb-2 text-lg font-bold text-white">{track.title}</h3>
              <p className="mb-4 text-sm leading-relaxed text-slate-400">{track.description}</p>
              <ul className="mt-auto space-y-2">
                {track.points.map((point) => (
                  <li key={point} className="flex items-center gap-2 text-xs text-slate-300">
                    <span className={`h-1.5 w-1.5 rounded-full ${track.accent.replace("text", "bg")}`} />
                    {point}
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </section>

        {/* AI assistant section */}
        <section className="py-12">
          <Card className="grid grid-cols-1 items-center gap-10 p-8 md:grid-cols-2 md:p-10">
            <div>
              <Badge tone="emerald" className="mb-4 gap-2">
                <Bot className="h-3.5 w-3.5" />
                Your AI assistant
              </Badge>
              <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                Advice you can trace back to your data
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-slate-400">
                Ask questions in plain language and get answers grounded in your own income,
                expenses, budgets and goals. Every response draws a clear line between{" "}
                <span className="font-semibold text-slate-200">facts</span> pulled from your records
                and <span className="font-semibold text-slate-200">estimates</span> the assistant
                projects — so you are never guessing where a number came from.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <InfoTile
                icon={<ShieldCheck className="h-5 w-5 text-emerald-300" />}
                tone="border-emerald-500/30 bg-emerald-500/10"
                title="Grounded"
                text="Answers built on your real transactions and profile."
              />
              <InfoTile
                icon={<Target className="h-5 w-5 text-indigo-300" />}
                tone="border-indigo-500/30 bg-indigo-500/10"
                title="Explainable"
                text="Facts and estimates are always labelled separately."
              />
              <InfoTile
                icon={<LineChart className="h-5 w-5 text-violet-300" />}
                tone="border-violet-500/30 bg-violet-500/10"
                title="Proactive"
                text="Recommendations come with the reasoning behind them."
              />
              <InfoTile
                icon={<Wallet className="h-5 w-5 text-sky-300" />}
                tone="border-sky-500/30 bg-sky-500/10"
                title="Deterministic"
                text="All financial math happens in the backend, not the model."
              />
            </div>
          </Card>
        </section>
      </main>

      {/* Footer */}
      <footer className="relative z-10 mt-8 border-t border-slate-800/80 py-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-4 px-6 text-xs text-slate-500 sm:flex-row">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-indigo-400" />
            <span>FinAgent — AI-Powered Financial Assistant</span>
          </div>
          <div className="flex items-center gap-5">
            <Link href="/login" className="transition-colors hover:text-slate-300">
              Sign in
            </Link>
            <Link href="/register" className="transition-colors hover:text-slate-300">
              Get started
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function InfoTile({
  icon,
  tone,
  title,
  text,
}: {
  icon: ReactNode;
  tone: string;
  title: string;
  text: string;
}) {
  return (
    <div className="glass-panel rounded-2xl p-4">
      <span className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl border ${tone}`}>
        {icon}
      </span>
      <h4 className="text-sm font-semibold text-white">{title}</h4>
      <p className="mt-1 text-xs leading-relaxed text-slate-400">{text}</p>
    </div>
  );
}
