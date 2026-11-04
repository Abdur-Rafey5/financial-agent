"""
Market data adapter with database-backed caching.

Quotes come from Alpha Vantage and are cached in ``market_data_snapshots`` so
we respect the provider's rate limits. Every response carries the provider name
and the timestamp of the underlying data. When no API key is configured we
return ``None`` instead of inventing prices.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.business import MarketDataSnapshot

logger = logging.getLogger(__name__)

PROVIDER = "Alpha Vantage"
_KEYLESS_PROVIDER = "Yahoo Finance"
_BASE_URL = "https://www.alphavantage.co/query"
_YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 FinAgent/1.0"}
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-^=]{1,20}$")

# Small curated list used only for the default watchlist *symbols*.
# No prices are attached to these.
DEFAULT_WATCHLIST = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "TSLA",
    "NVDA",
    "KO",  # Coca-Cola
    "PEP",  # PepsiCo
    "AMZN",
    "GC=F",  # COMEX gold futures (front-month)
    "^GSPC",  # S&P 500 index
]


class MarketDataError(RuntimeError):
    """Provider rejected or rate-limited the request."""


def is_configured() -> bool:
    return bool(settings.ALPHA_VANTAGE_API_KEY.strip())


def active_provider() -> str:
    """Name of the provider currently in use (surfaced without revealing keys)."""
    if is_configured():
        return PROVIDER
    if settings.MARKET_KEYLESS_FALLBACK:
        return _KEYLESS_PROVIDER
    return "none"


def normalize_symbol(symbol: str) -> str:
    symbol = (symbol or "").strip().upper()
    if not _SYMBOL_RE.match(symbol):
        raise ValueError("Invalid ticker symbol")
    return symbol


async def _cached(
    db: AsyncSession,
    symbol: str,
    data_type: str,
    ttl_seconds: int,
    *,
    provider: str = PROVIDER,
) -> Optional[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds)
    snapshot = await db.scalar(
        select(MarketDataSnapshot)
        .where(
            MarketDataSnapshot.symbol == symbol,
            MarketDataSnapshot.data_type == data_type,
            MarketDataSnapshot.provider == provider,
            MarketDataSnapshot.created_at >= cutoff,
        )
        .order_by(MarketDataSnapshot.created_at.desc())
        .limit(1)
    )
    if snapshot is None:
        return None
    return {
        "data": snapshot.data,
        "fetched_at": snapshot.created_at,
        "source_timestamp": snapshot.source_timestamp,
    }


async def _store(
    db: AsyncSession,
    symbol: str,
    data_type: str,
    data: dict[str, Any],
    source_timestamp: Optional[datetime] = None,
    *,
    provider: str = PROVIDER,
) -> None:
    db.add(
        MarketDataSnapshot(
            symbol=symbol,
            provider=provider,
            data_type=data_type,
            data=data,
            source_timestamp=source_timestamp,
        )
    )
    await db.commit()


async def _call_provider(params: dict[str, str]) -> dict[str, Any]:
    if not is_configured():
        raise MarketDataError("ALPHA_VANTAGE_API_KEY is not configured")
    query = {**params, "apikey": settings.ALPHA_VANTAGE_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(_BASE_URL, params=query)
    except httpx.HTTPError as exc:
        raise MarketDataError("Market data provider unreachable") from exc

    if response.status_code >= 400:
        raise MarketDataError(f"Provider returned HTTP {response.status_code}")

    payload = response.json()
    if "Note" in payload or "Information" in payload:
        raise MarketDataError("Provider rate limit reached")
    if "Error Message" in payload:
        raise MarketDataError(str(payload["Error Message"]))
    return payload


def _parse_quote(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    quote = payload.get("Global Quote") or {}
    if not quote.get("05. price"):
        return None
    price = float(quote["05. price"])
    change = float(quote.get("09. change") or 0)
    change_percent = float((quote.get("10. change percent") or "0").strip("%"))
    return {
        "symbol": quote.get("01. symbol"),
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "open": _to_float(quote.get("02. open")),
        "high": _to_float(quote.get("03. high")),
        "low": _to_float(quote.get("04. low")),
        "volume": int(float(quote.get("06. volume") or 0)),
        "latest_trading_day": quote.get("07. latest trading day"),
        "previous_close": _to_float(quote.get("08. previous close")),
    }


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "None"):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


async def get_quote(
    db: AsyncSession,
    symbol: str,
    *,
    force_refresh: bool = False,
) -> Optional[dict[str, Any]]:
    """
    Return a quote dict, or ``None`` when the provider is not configured.

    Raises :class:`MarketDataError` for provider/rate-limit failures.
    """
    symbol = normalize_symbol(symbol)

    if not force_refresh:
        cached = await _cached(db, symbol, "quote", settings.MARKET_DATA_CACHE_TTL_SECONDS)
        if cached:
            return _envelope(symbol, cached["data"], cached["fetched_at"], cached=False)

    if not is_configured():
        if settings.MARKET_KEYLESS_FALLBACK:
            return await _keyless_quote(db, symbol)
        return None

    payload = await _call_provider({"function": "GLOBAL_QUOTE", "symbol": symbol})
    data = _parse_quote(payload)
    if data is None:
        raise MarketDataError(f"No quote available for {symbol}")

    source_timestamp = None
    trading_day = data.get("latest_trading_day")
    if trading_day:
        try:
            source_timestamp = datetime.fromisoformat(trading_day).replace(tzinfo=timezone.utc)
        except ValueError:
            source_timestamp = None

    await _store(db, symbol, "quote", data, source_timestamp)
    return _envelope(symbol, data, datetime.now(timezone.utc), cached=False)


# ── Keyless Yahoo Finance fallback ──────────────────────────────────
async def _call_yahoo(path: str, params: dict[str, str]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_YAHOO_HEADERS) as client:
            response = await client.get(path, params=params)
    except httpx.HTTPError as exc:
        raise MarketDataError("Market data provider unreachable") from exc
    if response.status_code >= 400:
        raise MarketDataError(f"Provider returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise MarketDataError("Provider returned a non-JSON response") from exc


def _parse_yahoo_chart(payload: dict[str, Any]) -> dict[str, Any]:
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if result is None:
        raise MarketDataError("No quote available for this symbol")
    meta = result.get("meta") or {}

    price = _to_float(meta.get("regularMarketPrice"))
    if price is None:
        raise MarketDataError("No quote available for this symbol")

    # Derive the previous close from the daily closes in window.
    indicators = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [c for c in (indicators.get("close") or []) if c is not None]
    timestamps = result.get("timestamp") or []

    # Daily close history (aligned timestamp + close pairs); feeds the
    # deterministic trend calculations and the grounded AI insights.
    history = []
    for ts, close in zip(timestamps, indicators.get("close") or []):
        if ts is None or close is None:
            continue
        history.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc)
                .date()
                .isoformat(),
                "close": round(close, 2),
            }
        )

    previous_close = (
        _to_float(closes[-2])
        if len(closes) >= 2
        else _to_float(meta.get("chartPreviousClose"))
    )

    change = None
    change_percent = None
    if previous_close is not None and previous_close != 0:
        change = round(price - previous_close, 2)
        change_percent = round(change / previous_close * 100, 2)

    # Change across the whole fetched window (first vs last daily close).
    window_start = history[0]["close"] if history else None
    window_change_percent = None
    if window_start and len(history) >= 2 and window_start != 0:
        window_change_percent = round(
            (history[-1]["close"] - window_start) / window_start * 100, 2
        )

    trading_day: Optional[str] = None
    if timestamps:
        trading_day = datetime.fromtimestamp(
            timestamps[-1], tz=timezone.utc
        ).date().isoformat()

    return {
        "symbol": meta.get("symbol"),
        "price": round(price, 2),
        "change": change,
        "change_percent": change_percent,
        "open": _to_float((indicators.get("open") or [None])[-1]),
        "high": _to_float(meta.get("regularMarketDayHigh")),
        "low": _to_float(meta.get("regularMarketDayLow")),
        "volume": int(meta.get("regularMarketVolume") or 0),
        "latest_trading_day": trading_day,
        "previous_close": previous_close,
        "currency": meta.get("currency"),
        "history": history,
        "window_start": window_start,
        "window_change_percent": window_change_percent,
    }


async def _keyless_quote(db: AsyncSession, symbol: str) -> dict[str, Any]:
    """Fetch one quote from Yahoo Finance (no API key)."""
    payload = await _call_yahoo(
        _YAHOO_CHART_URL.format(symbol=symbol),
        params={"range": "5d", "interval": "1d"},
    )
    data = _parse_yahoo_chart(payload)

    source_timestamp = None
    if data.get("latest_trading_day"):
        try:
            source_timestamp = datetime.fromisoformat(
                data["latest_trading_day"]
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            source_timestamp = None

    await _store(
        db, symbol, "quote", data, source_timestamp, provider=_KEYLESS_PROVIDER
    )
    return {
        **data,
        "source": _KEYLESS_PROVIDER,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }


async def _keyless_search(query: str) -> list[dict[str, Any]]:
    """Symbol search via Yahoo Finance (no API key)."""
    payload = await _call_yahoo(
        _YAHOO_SEARCH_URL,
        params={"q": query, "quotesCount": 10},
    )
    matches = []
    for item in (payload.get("quotes") or [])[:10]:
        if not item.get("symbol"):
            continue
        matches.append(
            {
                "symbol": item.get("symbol"),
                "name": item.get("shortname") or item.get("longname"),
                "type": item.get("quoteType"),
                "region": item.get("exchDisp") or item.get("exchange"),
                "currency": item.get("currency"),
            }
        )
    return matches


def _envelope(
    symbol: str,
    data: dict[str, Any],
    fetched_at: datetime,
    *,
    cached: bool,
) -> dict[str, Any]:
    return {
        **data,
        "symbol": data.get("symbol") or symbol,
        "source": PROVIDER,
        "fetched_at": fetched_at.isoformat(),
        "cached": cached,
    }


async def search_symbols(
    db: AsyncSession,
    query: str,
) -> list[dict[str, Any]]:
    """Search ticker symbols. Returns an empty list when unconfigured."""
    query = (query or "").strip()
    if not query:
        return []

    cache_key = f"SEARCH:{query.upper()[:40]}"
    cached = await _cached(db, cache_key, "search", 86_400, provider=active_provider())
    if cached:
        return list(cached["data"].get("matches", []))

    if not is_configured():
        if settings.MARKET_KEYLESS_FALLBACK:
            matches = await _keyless_search(query)
            await _store(
                db,
                cache_key,
                "search",
                {"matches": matches},
                datetime.now(timezone.utc),
                provider=_KEYLESS_PROVIDER,
            )
            return matches
        return []

    payload = await _call_provider({"function": "SYMBOL_SEARCH", "keywords": query})
    matches = [
        {
            "symbol": item.get("1. symbol"),
            "name": item.get("2. name"),
            "type": item.get("3. type"),
            "region": item.get("4. region"),
            "currency": item.get("8. currency"),
        }
        for item in (payload.get("bestMatches") or [])[:10]
    ]
    await _store(db, cache_key, "search", {"matches": matches}, datetime.now(timezone.utc))
    return matches

