/**
 * Formatting helpers used across the dashboard.
 */

export function currencySymbol(code: string): string {
  const symbols: Record<string, string> = {
    PKR: "Rs",
    USD: "$",
    EUR: "€",
    GBP: "£",
    INR: "₹",
    AED: "د.إ",
    SAR: "﷼",
  };
  return symbols[code] ?? code;
}

export function formatMoney(value: number | null | undefined, currency = "PKR"): string {
  const amount = Number(value ?? 0);
  const formatted = amount.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const symbol = currencySymbol(currency);
  const spaced = symbol.length > 1 ? " " : "";
  return `${symbol}${spaced}${formatted}`;
}

export function formatPercent(value: number | null | undefined): string {
  return `${Number(value ?? 0).toFixed(1)}%`;
}

export function formatNumber(value: number | null | undefined): string {
  return Number(value ?? 0).toLocaleString("en-US");
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Trend months arrive as e.g. "Nov 2026" — display as-is with first capital. */
export function formatMonth(month: string): string {
  return month.charAt(0).toUpperCase() + month.slice(1);
}

export function todayISO(): string {
  const now = new Date();
  const offsetLocal = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return offsetLocal.toISOString().slice(0, 10);
}

export function currentMonthStartISO(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

export function addDaysISO(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}
