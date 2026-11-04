/**
 * API client library with automatic JWT token attachment and error handling.
 */

import type {
  AssistantMessage,
  AuthResponse,
  BusinessProfile,
  BusinessSummary,
  BusinessSummaryProfileCreate,
  CashFlowResponse,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  DashboardSummary,
  DemoCredentials,
  ExpenseRecord,
  Goal,
  IncomeCategory,
  IncomeRecord,
  MarketStatus,
  InsightsResponse,
  OnboardingPayload,
  Recommendation,
  RecommendationList,
  GenerateResult,
  ReportAnalytics,
  Scenario,
  SearchResponse,
  UserProfile,
  WatchlistResponse,
  QuoteEnvelope,
  Budget,
  BudgetInput,
  BudgetPatch,
  GoalInput,
  GoalPatch,
  TransactionList,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ── Token + user storage ──────────────────────────────────────────────
export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function setStoredToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("token", token);
  }
}

export function clearStoredToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  }
}

export function setStoredUser(user: unknown): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("user", JSON.stringify(user));
  }
}

export function getStoredUser(): UserProfile | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("user");
    return raw ? (JSON.parse(raw) as UserProfile) : null;
  } catch {
    return null;
  }
}

interface ApiErrorBody {
  detail?: unknown;
  message?: string;
}

function extractError(body: ApiErrorBody | null): string {
  if (!body) return "An unexpected error occurred.";
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    const first = body.detail[0] as { message?: string; msg?: string };
    return first?.message || first?.msg || "Request validation failed.";
  }
  return body.message || "An unexpected error occurred.";
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      // non-JSON error body
    }
    throw new Error(extractError(body));
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json() as Promise<T>;
}

const qs = (params: Record<string, string | number | boolean | undefined>) => {
  const usable = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (!usable.length) return "";
  return `?${new URLSearchParams(
    Object.fromEntries(usable.map(([k, v]) => [k, String(v)]))
  ).toString()}`;
};

// ── Auth ──────────────────────────────────────────────────────────────
export const authApi = {
  register: (payload: { full_name: string; email: string; password: string }) =>
    apiFetch<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  login: (payload: { email: string; password: string }) =>
    apiFetch<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  demo: () => apiFetch<AuthResponse>("/auth/demo", { method: "POST" }),
  demoCredentials: () => apiFetch<DemoCredentials>("/auth/demo/credentials"),
  logout: () => apiFetch<{ message: string }>("/auth/logout", { method: "POST" }),
  me: () => apiFetch<UserProfile>("/auth/me"),
};

// ── Users / onboarding ────────────────────────────────────────────────
export const usersApi = {
  me: () => apiFetch<UserProfile>("/users/me"),
  updateMe: (payload: Partial<UserProfile>) =>
    apiFetch<UserProfile>("/users/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  onboarding: (payload: OnboardingPayload) =>
    apiFetch<UserProfile>("/users/onboarding", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// ── Categories ────────────────────────────────────────────────────────
export const categoryApi = {
  expenseCategories: () =>
    apiFetch<{ id: string; name: string; is_system: boolean }[]>("/expenses/categories"),
  incomeCategories: () =>
    apiFetch<IncomeCategory[]>("/income/categories"),
  createExpenseCategory: (name: string) =>
    apiFetch<{ id: string; name: string; is_system: boolean }>("/expenses/categories", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  deleteExpenseCategory: (id: string) =>
    apiFetch<void>(`/expenses/categories/${id}`, { method: "DELETE" }),
  createIncomeCategory: (name: string) =>
    apiFetch<IncomeCategory>("/income/categories", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
};

// ── Income ────────────────────────────────────────────────────────────
export const incomeApi = {
  list: (params: {
    start_date?: string;
    end_date?: string;
    income_type?: string;
    search?: string;
    limit?: number;
    offset?: number;
  } = {}) =>
    apiFetch<TransactionList<IncomeRecord>>(
      `/income${qs(params)}`
    ),
  get: (id: string) => apiFetch<IncomeRecord>(`/income/${id}`),
  create: (payload: {
    amount: number;
    currency: string;
    date: string;
    source: string;
    income_type: string;
    category_id?: string;
    frequency?: string;
    notes?: string;
  }) =>
    apiFetch<IncomeRecord>("/income", { method: "POST", body: JSON.stringify(payload) }),
  update: (
    id: string,
    payload: Partial<{
      amount: number;
      currency: string;
      date: string;
      source: string;
      income_type: string;
      category_id: string | null;
      frequency: string | null;
      notes: string | null;
    }>
  ) => apiFetch<IncomeRecord>(`/income/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delete: (id: string) => apiFetch<void>(`/income/${id}`, { method: "DELETE" }),
};

// ── Expenses ──────────────────────────────────────────────────────────
export const expenseApi = {
  list: (params: {
    start_date?: string;
    end_date?: string;
    category_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  } = {}) =>
    apiFetch<TransactionList<ExpenseRecord>>(`/expenses${qs(params)}`),
  get: (id: string) => apiFetch<ExpenseRecord>(`/expenses/${id}`),
  create: (payload: {
    amount: number;
    currency: string;
    date: string;
    description: string;
    category_id?: string | null;
    notes?: string;
  }) =>
    apiFetch<ExpenseRecord>("/expenses", { method: "POST", body: JSON.stringify(payload) }),
  update: (
    id: string,
    payload: Partial<{
      amount: number;
      currency: string;
      date: string;
      description: string;
      category_id: string | null;
      notes: string | null;
    }>
  ) => apiFetch<ExpenseRecord>(`/expenses/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delete: (id: string) => apiFetch<void>(`/expenses/${id}`, { method: "DELETE" }),
};

// ── Budgets ───────────────────────────────────────────────────────────
export const budgetsApi = {
  list: (activeOnly = false) =>
    apiFetch<Budget[]>(`/budgets${qs({ active_only: activeOnly || undefined })}`),
  get: (id: string) => apiFetch<Budget>(`/budgets/${id}`),
  create: (payload: BudgetInput) =>
    apiFetch<Budget>("/budgets", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: string, payload: BudgetPatch) =>
    apiFetch<Budget>(`/budgets/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delete: (id: string) => apiFetch<void>(`/budgets/${id}`, { method: "DELETE" }),
};

// ── Goals ─────────────────────────────────────────────────────────────
export const goalsApi = {
  list: () => apiFetch<Goal[]>("/goals"),
  get: (id: string) => apiFetch<Goal>(`/goals/${id}`),
  create: (payload: GoalInput) =>
    apiFetch<Goal>("/goals", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: string, payload: GoalPatch) =>
    apiFetch<Goal>(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delete: (id: string) => apiFetch<void>(`/goals/${id}`, { method: "DELETE" }),
  contribute: (id: string, payload: { amount: number; date: string; notes?: string }) =>
    apiFetch<Goal>(`/goals/${id}/contribute`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteContribution: (goalId: string, contributionId: string) =>
    apiFetch<Goal>(`/goals/${goalId}/contributions/${contributionId}`, {
      method: "DELETE",
    }),
};

// ── Dashboard ─────────────────────────────────────────────────────────
export const dashboardApi = {
  summary: () => apiFetch<DashboardSummary>("/dashboard/summary"),
};

// ── Reports ───────────────────────────────────────────────────────────
export const reportsApi = {
  analytics: (params: { start_date?: string; end_date?: string } = {}) =>
    apiFetch<ReportAnalytics>(`/reports/analytics${qs(params)}`),
};

// ── Assistant ─────────────────────────────────────────────────────────
export const assistantApi = {
  chat: (payload: { message: string; conversation_id?: string | null }) =>
    apiFetch<ChatResponse>("/assistant/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  conversations: (limit = 20) =>
    apiFetch<ConversationSummary[]>(`/assistant/conversations${qs({ limit })}`),
  conversation: (id: string) =>
    apiFetch<ConversationDetail>(`/assistant/conversations/${id}`),
  deleteConversation: (id: string) =>
    apiFetch<void>(`/assistant/conversations/${id}`, { method: "DELETE" }),
};

// ── Recommendations ───────────────────────────────────────────────────
export const recommendationsApi = {
  list: (params: { unread_only?: boolean; type?: string; priority?: string } = {}) =>
    apiFetch<RecommendationList>(`/recommendations${qs(params)}`),
  generate: (force = false) =>
    apiFetch<GenerateResult>(`/recommendations/generate${qs({ force })}`, {
      method: "POST",
    }),
  markRead: (id: string) =>
    apiFetch<Recommendation>(`/recommendations/${id}/read`, { method: "PATCH" }),
  dismiss: (id: string) =>
    apiFetch<void>(`/recommendations/${id}/dismiss`, { method: "PATCH" }),
  readAll: () =>
    apiFetch<RecommendationList>("/recommendations/read-all", { method: "PATCH" }),
};

// ── Investments ───────────────────────────────────────────────────────
export const investmentsApi = {
  status: () => apiFetch<MarketStatus>("/investments/status"),
  quote: (symbol: string, force = false) =>
    apiFetch<QuoteEnvelope>(
      `/investments/quotes/${encodeURIComponent(symbol)}${qs({ force_refresh: force || undefined })}`
    ),
  watchlist: () => apiFetch<WatchlistResponse>("/investments/watchlist"),
  insights: () => apiFetch<InsightsResponse>("/investments/insights"),
  search: (query: string) =>
    apiFetch<SearchResponse>(`/investments/search${qs({ q: query })}`),
};

// ── Business ──────────────────────────────────────────────────────────
export const businessApi = {
  getProfile: () => apiFetch<BusinessProfile | null>("/business/profile"),
  upsertProfile: (payload: BusinessSummaryProfileCreate) =>
    apiFetch<BusinessProfile>("/business/profile", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProfile: (payload: Partial<BusinessSummaryProfileCreate>) =>
    apiFetch<BusinessProfile>("/business/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  summary: () => apiFetch<BusinessSummary>("/business/summary"),
  cashFlow: (months = 6) =>
    apiFetch<CashFlowResponse>(`/business/cash-flow${qs({ months })}`),
  scenarios: () => apiFetch<Scenario[]>("/business/scenarios"),
  getScenario: (id: string) => apiFetch<Scenario>(`/business/scenarios/${id}`),
  createScenario: (payload: {
    title: string;
    scenario_type?: string;
    description?: string;
    assumptions: Record<string, number>;
  }) => apiFetch<Scenario>("/business/scenarios", { method: "POST", body: JSON.stringify(payload) }),
  updateScenario: (
    id: string,
    payload: Partial<{
      title: string;
      scenario_type: string;
      description: string;
      assumptions: Record<string, number>;
    }>
  ) =>
    apiFetch<Scenario>(`/business/scenarios/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteScenario: (id: string) =>
    apiFetch<void>(`/business/scenarios/${id}`, { method: "DELETE" }),
};
