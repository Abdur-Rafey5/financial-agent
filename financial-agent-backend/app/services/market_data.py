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
_BASE_URL = "https://www.alphavantage.co/query"
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]{1,20}$")

# Small curated list used only for the default watchlist *symbols*.
# No prices are attached to these.
DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]


class MarketDataError(RuntimeError):
    """Provider rejected or rate-limited the request."""


def is_configured() -> bool:
    return bool(settings.ALPHA_VANTAGE_API_KEY.strip())


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
) -> Optional[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds)
    snapshot = await db.scalar(
        select(MarketDataSnapshot)
        .where(
            MarketDataSnapshot.symbol == symbol,
            MarketDataSnapshot.data_type == data_type,
            MarketDataSnapshot.provider == PROVIDER,
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
) -> None:
    db.add(
        MarketDataSnapshot(
            symbol=symbol,
            provider=PROVIDER,
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
    cached = await _cached(db, cache_key, "search", 86_400)
    if cached:
        return list(cached["data"].get("matches", []))

    if not is_configured():
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

