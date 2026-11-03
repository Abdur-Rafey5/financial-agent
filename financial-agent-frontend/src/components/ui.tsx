"use client";

import clsx from "clsx";
import { twMerge } from "tailwind-merge";
import {
  forwardRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { AlertCircle, Loader2, X } from "lucide-react";

export function cn(...inputs: (string | undefined | false | null)[]): string {
  return twMerge(clsx(inputs));
}

// ── Tone palette ──────────────────────────────────────────────────────
const TONES = {
  indigo: "bg-indigo-500/10 text-indigo-300 border-indigo-500/20",
  emerald: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  red: "bg-red-500/10 text-red-300 border-red-500/20",
  amber: "bg-amber-500/10 text-amber-300 border-amber-500/20",
  sky: "bg-sky-500/10 text-sky-300 border-sky-500/20",
  violet: "bg-violet-500/10 text-violet-300 border-violet-500/20",
  slate: "bg-slate-500/10 text-slate-300 border-slate-500/20",
} as const;

export type Tone = keyof typeof TONES;

// ── Badge ─────────────────────────────────────────────────────────────
export function Badge({
  tone = "slate",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize",
        TONES[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

// ── Button ────────────────────────────────────────────────────────────
const BUTTON_VARIANTS = {
  primary:
    "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/25",
  secondary:
    "bg-slate-800/80 hover:bg-slate-700 text-slate-100 border border-slate-700",
  ghost: "bg-transparent hover:bg-slate-800/60 text-slate-200",
  danger: "bg-red-600/90 hover:bg-red-500 text-white",
} as const;

const BUTTON_SIZES = {
  sm: "px-3 py-1.5 text-xs rounded-lg",
  md: "px-4 py-2.5 text-sm rounded-xl",
  lg: "px-6 py-3.5 text-sm rounded-xl",
} as const;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof BUTTON_VARIANTS;
  size?: keyof typeof BUTTON_SIZES;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, className, children, disabled, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60 disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className
      )}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
});

// ── Card ──────────────────────────────────────────────────────────────
export function Card({
  children,
  className,
  hover,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <div
      className={cn(
        "glass-panel rounded-2xl p-6",
        hover && "glass-panel-hover",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <h3 className="flex items-center gap-2 text-base font-bold text-white">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────
const STAT_ICONS: Record<Tone, string> = {
  indigo: "from-indigo-500/25 to-indigo-500/5 text-indigo-300",
  emerald: "from-emerald-500/25 to-emerald-500/5 text-emerald-300",
  red: "from-red-500/25 to-red-500/5 text-red-300",
  amber: "from-amber-500/25 to-amber-500/5 text-amber-300",
  sky: "from-sky-500/25 to-sky-500/5 text-sky-300",
  violet: "from-violet-500/25 to-violet-500/5 text-violet-300",
  slate: "from-slate-500/25 to-slate-500/5 text-slate-300",
};

export function StatCard({
  label,
  value,
  sub,
  icon,
  tone = "indigo",
  className,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  icon?: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "glass-panel glass-panel-hover relative overflow-hidden rounded-2xl p-5",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            {label}
          </p>
          <p className="mt-2 truncate text-2xl font-bold text-white">{value}</p>
          {sub && <p className="mt-1 text-[11px] text-slate-500">{sub}</p>}
        </div>
        {icon && (
          <span
            className={cn(
              "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br",
              STAT_ICONS[tone]
            )}
          >
            {icon}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Progress bar ──────────────────────────────────────────────────────
export function ProgressBar({
  value,
  tone,
  className,
}: {
  value: number;
  tone?: Tone;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, value));
  const auto: Tone = value >= 100 ? "red" : value >= 80 ? "amber" : value >= 50 ? "indigo" : "emerald";
  const bar: Record<Tone, string> = {
    indigo: "bg-indigo-500",
    emerald: "bg-emerald-500",
    red: "bg-red-500",
    amber: "bg-amber-500",
    sky: "bg-sky-500",
    violet: "bg-violet-500",
    slate: "bg-slate-500",
  };
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-slate-800", className)}>
      <div
        className={cn("h-full rounded-full transition-all", bar[tone ?? auto])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Form fields ───────────────────────────────────────────────────────
const FIELD_CLASS =
  "w-full rounded-xl border border-slate-700/80 bg-slate-900/60 px-4 py-2.5 text-sm text-white placeholder:text-slate-500 outline-none transition-all focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={cn(FIELD_CLASS, className)} {...rest} />;
  }
);

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...rest }, ref) {
  return (
    <select
      ref={ref}
      className={cn(FIELD_CLASS, "appearance-none bg-slate-900", className)}
      {...rest}
    >
      {children}
    </select>
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cn(FIELD_CLASS, "resize-none", className)} {...rest} />;
});

export function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-semibold text-slate-300">
        {label}
        {required && <span className="ml-1 text-red-400">*</span>}
        {hint && <span className="ml-2 font-normal text-slate-500">{hint}</span>}
      </label>
      {children}
    </div>
  );
}

// ── States ────────────────────────────────────────────────────────────
export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 rounded-2xl border border-slate-800/60 bg-slate-900/30 py-16 text-sm text-slate-400">
      <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
      {label}
    </div>
  );
}

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      <span className="flex items-center gap-3">
        <AlertCircle className="h-5 w-5 flex-shrink-0" />
        {message}
      </span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex-shrink-0 font-semibold text-red-200 underline-offset-2 hover:underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-700/60 px-6 py-12 text-center">
      {icon && (
        <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-800/60 text-slate-400">
          {icon}
        </span>
      )}
      <h4 className="text-sm font-semibold text-white">{title}</h4>
      {description && (
        <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────
export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="glass-panel relative z-10 w-full max-w-lg rounded-2xl p-6 shadow-2xl">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-white">{title}</h3>
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
        {footer && (
          <div className="mt-6 flex items-center justify-end gap-3">{footer}</div>
        )}
      </div>
    </div>
  );
}

// ── Section helper ────────────────────────────────────────────────────
export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
      {children}
    </h2>
  );
}
