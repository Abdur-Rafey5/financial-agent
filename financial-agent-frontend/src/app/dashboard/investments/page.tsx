"use client";

import { useCallback, useEffect, useState } from "react";
import { Info, RefreshCw, Search, TrendingDown, TrendingUp } from "lucide-react";
import { investmentsApi } from "@/lib/api";
import type {
  MarketStatus,
  QuoteData,
  QuoteEnvelope,
  SearchResponse,
  WatchlistResponse,
} from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorBanner,
  Input,
  LoadingBlock,
  StatCard,
} from "@/components/ui";
import { PageHeader } from "@/components/app-shell";
import { formatDate, formatNumber, formatDateTime } from "@/lib/format";

function ChangeBadge({ quote }: { quote: QuoteData }) {
  const change = quote.change_percent;
  if (change === null || change === undefined) return null;
  const up = change >= 0;
  return (
    <Badge tone={up ? "emerald" : "red"}>
      {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {up ? "+" : ""}
      {change.toFixed(2)}%
    </Badge>
  );
}

export default function InvestmentsPage() {
  const [status, setStatus] = useState<MarketStatus | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ refreshing, setRefreshing ] = useState(false);

  const [query, setQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);

  const [selected, setSelected] = useState<QuoteEnvelope | null>(null);
  const [selectedLoading, setSelectedLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusRes, watchlistRes] = await Promise.all([
        investmentsApi.status(),
        investmentsApi.watchlist(),
      ]);
      setStatus(statusRes);
      setWatchlist(watchlistRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load investment data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const configured = watchlist?.configured ?? false;

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearchResult(null);
    try {
      setSearchResult(await investmentsApi.search(query.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Symbol search failed.");
    } finally {
      setSearching(false);
    }
  };

  const openQuote = async (symbol: string, force = false) => {
    setSelectedLoading(true);
    setError(null);
    try {
      setSelected(await investmentsApi.quote(symbol, force));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Quote lookup failed.");
    } finally {
      setSelectedLoading(false);
    }
  };

  const refreshAll = async () => {
    setRefreshing(true);
    try {
      setWatchlist(await investmentsApi.watchlist());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed.");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div>
      <PageHeader
        icon={<TrendingUp className="h-6 w-6" />}
        title="Investments"
        description="Real market quotes with source and timestamp — unavailable (never simulated) when no provider is configured."
      />

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} onRetry={() => void load()} />
        </div>
      )}

      {/* Provider status banner */}
      <div
        className={`mb-6 flex items-start gap-3 rounded-xl border px-4 py-3 text-xs ${
          configured
            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200"
            : "border-amber-500/20 bg-amber-500/10 text-amber-200"
        }`}
      >
        <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <div>
          <p>{status?.message ?? "Checking market-data provider…"}</p>
          <p className="mt-1 text-[11px] opacity-80">
            Provider: {status?.provider ?? "—"} · Cache TTL: {formatNumber(status?.cache_ttl_seconds ?? 0)}s
            · Watchlist: {(status?.watchlist_symbols ?? []).join(", ") || "—"}
          </p>
        </div>
      </div>

      {/* Symbol lookup */}
      <Card className="mb-6">
        <CardHeader
          title="Look up a quote"
          subtitle="Enter a ticker symbol, e.g. AAPL or MSFT — quotes come from the active market-data provider."
        />
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === "Enter") void search();
            }}
            placeholder="AAPL"
            maxLength={40}
            className="sm:w-56"
          />
          <Button onClick={() => void search()} loading={searching}>
            <Search className="h-4 w-4" /> Search
          </Button>
        </div>

        {searchResult && (
          <div className="mt-4">
            {!searchResult.available ? (
              <p className="text-xs text-amber-200">{searchResult.reason}</p>
            ) : searchResult.results.length ? (
              <div className="space-y-2">
                {searchResult.results.slice(0, 6).map((result) => (
                  <div
                    key={`${result.symbol}-${result.name}`}
                    className="flex items-center justify-between gap-3 rounded-xl border border-slate-800/70 px-4 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white">{result.symbol}</p>
                      <p className="truncate text-xs text-slate-500">
                        {result.name ?? "—"}
                        {result.type ? ` · ${result.type}` : ""}
                        {result.region ? ` · ${result.region}` : ""}
                      </p>
                    </div>
                    <Button size="sm" variant="secondary" onClick={() => void openQuote(result.symbol)}>
                      Get quote
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-3 text-center text-xs text-slate-500">No matching symbols found.</p>
            )}
          </div>
        )}

        {selectedLoading && (
          <div className="mt-4">
            <LoadingBlock label="Fetching quote…" />
          </div>
        )}

        {selected && !selectedLoading && (
          <div className="mt-4 rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-5">
            {!selected.available || !selected.quote ? (
              <p className="text-sm text-amber-200">{selected.reason ?? "Quote unavailable."}</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-lg font-bold text-white">
                      {selected.quote.symbol} · {selected.quote.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Source: {selected.source} · Fetched: {formatDateTime(selected.fetched_at)}
                      {selected.cached ? " (cached)" : " (live)"}
                      {selected.quote.latest_trading_day
                        ? ` · Trading day: ${formatDate(selected.quote.latest_trading_day)}`
                        : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <ChangeBadge quote={selected.quote} />
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => void openQuote(selected.symbol, true)}
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> Refresh
                    </Button>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-5">
                  {[
                    ["Open", selected.quote.open],
                    ["High", selected.quote.high],
                    ["Low", selected.quote.low],
                    ["Prev close", selected.quote.previous_close],
                    ["Volume", selected.quote.volume],
                  ].map(([label, value]) => (
                    <div key={label as string} className="rounded-xl bg-slate-900/50 px-3 py-2.5">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
                      <p className="mt-1 font-semibold text-slate-200">
                        {value === null || value === undefined ? "—" : formatNumber(value as number)}
                      </p>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </Card>

      {/* Watchlist */}
      {loading ? (
        <LoadingBlock label="Loading watchlist…" />
      ) : (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Watchlist
            </h2>
            {configured && (
              <Button size="sm" variant="secondary" onClick={() => void refreshAll()} loading={refreshing}>
                <RefreshCw className="h-3.5 w-3.5" /> Refresh all
              </Button>
            )}
          </div>

          {watchlist?.items.length ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {watchlist.items.map((item) => (
                <Card key={item.symbol} hover={item.available}>
                  {item.available && item.quote ? (
                    <button
                      type="button"
                      onClick={() => void openQuote(item.quote!.symbol)}
                      className="w-full text-left"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-base font-bold text-white">{item.symbol}</p>
                        <ChangeBadge quote={item.quote} />
                      </div>
                      <p className="mt-2 text-2xl font-bold text-slate-100">
                        {item.quote.price.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                      </p>
                      <p className="mt-2 text-[11px] text-slate-500">
                        {formatDateTime(item.fetched_at)}
                        {item.cached ? " (cached)" : " (live)"} · {item.quote.latest_trading_day ?? ""}
                      </p>
                    </button>
                  ) : (
                    <div>
                      <p className="text-base font-bold text-white">{item.symbol}</p>
                      <p className="mt-2 text-xs leading-relaxed text-amber-200">
                        {item.reason ?? "Quote unavailable."}
                      </p>
                      <p className="mt-1 text-[10px] text-slate-600">
                        No data is shown rather than an invented price.
                      </p>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-slate-500">Watchlist is empty.</p>
          )}
        </div>
      )}
    </div>
  );
}
