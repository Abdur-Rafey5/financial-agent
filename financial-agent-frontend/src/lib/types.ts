/**
 * Shared TypeScript types mirroring the FastAPI response schemas.
 */

export type Category = "student" | "employee" | "businessman";

export type IncomeType =
  | "salary"
  | "allowance"
  | "freelance"
  | "business_revenue"
  | "investment"
  | "gift"
  | "refund"
  | "other";

export type IncomeFrequency =
  | "one_time"
  | "daily"
  | "weekly"
  | "biweekly"
  | "monthly"
  | "quarterly"
  | "yearly";

// ── Auth / users ──────────────────────────────────────────────────────
export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  has_profile: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface DemoCredentials {
  email: string;
  password: string;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  category: Category | null;
  currency: string;
  onboarding_completed: boolean;
  allowance_amount?: number | null;
  allowance_frequency?: string | null;
  monthly_salary?: number | null;
  employer_name?: string | null;
}

export interface OnboardingPayload {
  category: Category;
  currency: string;
  allowance_amount?: number;
  allowance_frequency?: string;
  monthly_salary?: number;
  employer_name?: string;
}

// ── Categories ────────────────────────────────────────────────────────
export interface ExpenseCategory {
  id: string;
  name: string;
  is_system: boolean;
  icon?: string | null;
  color?: string | null;
}

export interface IncomeCategory {
  id: string;
  name: string;
  is_system: boolean;
}

// ── Transactions ──────────────────────────────────────────────────────
export interface IncomeRecord {
  id: string;
  amount: number;
  currency: string;
  date: string;
  source: string;
  income_type: string;
  category_id?: string | null;
  frequency?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransactionList<T> {
  items: T[];
  total: number;
  total_amount: number;
}

export interface ExpenseRecord {
  id: string;
  amount: number;
  currency: string;
  date: string;
  description: string;
  category_id?: string | null;
  category_name?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

// ── Budgets ───────────────────────────────────────────────────────────
export interface BudgetAllocation {
  id: string;
  category_id: string;
  category_name?: string | null;
  limit_amount: number;
  spent_amount: number;
  usage_pct: number;
}

export interface Budget {
  id: string;
  name: string;
  period_type: string;
  start_date: string;
  end_date: string;
  total_limit: number;
  total_spent: number;
  remaining_amount: number;
  usage_pct: number;
  is_active: boolean;
  currency: string;
  allocations: BudgetAllocation[];
  created_at: string;
  updated_at: string;
}

export interface BudgetAllocationInput {
  category_id: string;
  limit_amount: number;
}

export interface BudgetInput {
  name: string;
  period_type?: string;
  start_date: string;
  end_date: string;
  total_limit: number;
  currency?: string;
  category_allocations?: BudgetAllocationInput[];
}

export interface BudgetPatch {
  name?: string;
  period_type?: string;
  start_date?: string;
  end_date?: string;
  total_limit?: number;
  currency?: string;
  category_allocations?: BudgetAllocationInput[];
}

// ── Goals ─────────────────────────────────────────────────────────────
export interface GoalContribution {
  id: string;
  goal_id: string;
  amount: number;
  date: string;
  notes?: string | null;
  created_at: string;
}

export interface Goal {
  id: string;
  title: string;
  description?: string | null;
  target_amount: number;
  current_amount: number;
  percentage_completed: number;
  remaining_amount: number;
  currency: string;
  target_date?: string | null;
  status: string;
  contributions: GoalContribution[];
  created_at: string;
  updated_at: string;
}

export interface GoalInput {
  title: string;
  description?: string;
  target_amount: number;
  currency?: string;
  target_date?: string;
}

export interface GoalPatch {
  title?: string;
  description?: string;
  target_amount?: number;
  currency?: string;
  target_date?: string;
  status?: string;
}

// ── Dashboard ─────────────────────────────────────────────────────────
export interface TopCategory {
  name: string;
  color?: string | null;
  amount: number;
  percentage: number;
}

export interface RecentTransaction {
  id: string;
  type: "income" | "expense";
  description: string;
  amount: number;
  date: string;
  category?: string | null;
}

export interface TrendPoint {
  month: string;
  income: number;
  expenses: number;
  net: number;
}

export interface ContextGoal {
  id: string;
  title: string;
  target: number;
  current: number;
  progress_pct: number;
  status: string;
  target_date?: string | null;
  days_left?: number | null;
}

export interface ContextBudget {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  limit: number;
  spent: number;
  remaining: number;
  usage_pct: number;
  is_active: boolean;
  allocations: { category: string; limit: number; spent: number }[];
}

export interface BusinessInfo {
  name: string;
  type?: string | null;
  industry?: string | null;
  available_capital: number;
  currency: string;
}

export interface DashboardSummary {
  category: string;
  currency: string;
  period_start: string;
  period_end: string;
  total_income_this_month: number;
  total_expenses_this_month: number;
  net_savings_this_month: number;
  savings_rate_pct: number;
  previous_month_expenses: number;
  expense_change_pct: number;
  top_expense_categories: TopCategory[];
  recent_transactions: RecentTransaction[];
  active_goals_count: number;
  active_budgets_count: number;
  unread_recommendations_count: number;
  category_metrics: Record<string, number | boolean>;
  goals: ContextGoal[];
  budgets: ContextBudget[];
  trend: TrendPoint[];
  business: BusinessInfo | null;
}

// ── Reports ───────────────────────────────────────────────────────────
export interface BreakdownItem {
  key: string;
  label: string;
  amount: number;
  percentage: number;
  color: string;
}

export interface ReportMonth {
  month: string;
  month_start: string;
  income: number;
  expense: number;
  net_savings: number;
}

export interface ReportAnalytics {
  start_date: string;
  end_date: string;
  months: number;
  total_income: number;
  total_expenses: number;
  net_savings: number;
  savings_rate_pct: number;
  average_monthly_expenses: number;
  top_expense_category?: string | null;
  category_breakdown: BreakdownItem[];
  income_breakdown: BreakdownItem[];
  monthly_trend: ReportMonth[];
}

// ── Assistant ─────────────────────────────────────────────────────────
export interface AssistantMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface ChatResponse {
  conversation_id: string;
  message: AssistantMessage;
  ai_generated: boolean;
  context_period: string;
}

export interface ConversationSummary {
  id: string;
  title?: string | null;
  message_count: number;
  last_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title?: string | null;
  messages: AssistantMessage[];
  created_at: string;
  updated_at: string;
}

// ── Recommendations ───────────────────────────────────────────────────
export interface Recommendation {
  id: string;
  type: string;
  title: string;
  content: string;
  reasoning?: string | null;
  priority: string;
  is_read: boolean;
  is_dismissed: boolean;
  source_data?: Record<string, unknown> | null;
  created_at: string;
}

export interface RecommendationList {
  items: Recommendation[];
  total: number;
  unread_count: number;
}

export interface GenerateResult {
  created: number;
  items: Recommendation[];
}

// ── Investments ───────────────────────────────────────────────────────
export interface QuoteData {
  symbol: string;
  price: number;
  change?: number | null;
  change_percent?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  previous_close?: number | null;
  volume?: number | null;
  latest_trading_day?: string | null;
}

export interface QuoteEnvelope {
  available: boolean;
  symbol: string;
  provider: string;
  source: string;
  fetched_at?: string | null;
  cached: boolean;
  reason?: string | null;
  quote?: QuoteData | null;
}

export interface WatchlistItem {
  symbol: string;
  available: boolean;
  reason?: string | null;
  quote?: QuoteData | null;
  fetched_at?: string | null;
  cached: boolean;
}

export interface WatchlistResponse {
  provider: string;
  configured: boolean;
  items: WatchlistItem[];
}

export interface SearchResult {
  symbol: string;
  name?: string | null;
  type?: string | null;
  region?: string | null;
  currency?: string | null;
}

export interface SearchResponse {
  available: boolean;
  provider: string;
  reason?: string | null;
  results: SearchResult[];
}

export interface MarketStatus {
  configured: boolean;
  provider: string;
  cache_ttl_seconds: number;
  watchlist_symbols: string[];
  message: string;
}

// ── Business ──────────────────────────────────────────────────────────
export interface BusinessProfile {
  id: string;
  business_name: string;
  business_type?: string | null;
  industry?: string | null;
  available_capital?: number | null;
  currency: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PeriodMetrics {
  start_date: string;
  end_date: string;
  revenue: number;
  expenses: number;
  profit: number;
  margin_pct: number;
  transaction_count: number;
}

export interface BusinessSummary {
  business: BusinessProfile;
  currency: string;
  current_month: PeriodMetrics;
  year_to_date: PeriodMetrics;
  available_capital: number;
  monthly_trend: {
    month: string;
    month_start: string;
    revenue: number;
    expenses: number;
    profit: number;
  }[];
  revenue_basis: string;
  expense_basis: string;
}

export interface CashFlowMonth {
  month: string;
  month_start: string;
  revenue: number;
  expenses: number;
  net_cash_flow: number;
}

export interface CashFlowResponse {
  currency: string;
  months: CashFlowMonth[];
  average_monthly_net: number;
  positive_months: number;
  negative_months: number;
  available_capital: number;
  runway_months?: number | null;
  revenue_basis: string;
  expense_basis: string;
}

export interface ScenarioResult {
  initial_cost: number;
  horizon_months: number;
  monthly_growth_pct: number;
  projected_revenue: number;
  projected_costs: number;
  projected_net_profit: number;
  projected_roi_pct?: number | null;
  break_even_month?: number | null;
  monthly_projection: {
    month: number;
    gross_return: number;
    operating_cost: number;
    net: number;
    cumulative: number;
  }[];
}

export interface Scenario {
  id: string;
  business_id: string;
  title: string;
  scenario_type: string;
  description?: string | null;
  assumptions?: Record<string, unknown> | null;
  results?: ScenarioResult | null;
  ai_analysis?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BusinessSummaryProfileCreate {
  business_name: string;
  business_type?: string;
  industry?: string;
  available_capital?: number;
  currency?: string;
  description?: string;
}
