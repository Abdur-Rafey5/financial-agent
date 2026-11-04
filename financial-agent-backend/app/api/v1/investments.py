"""
Investments and market-data API.

Quotes come from Alpha Vantage through :mod:`app.services.market_data`, with an
optional keyless Yahoo Finance fallback (``MARKET_KEYLESS_FALLBACK=true``).
When no provider is available, or the provider fails or rate-limits the
request, the response says so explicitly. Prices are never fabricated.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import settings
from app.services import gemini, market_data
from datetime import datetime, timezone

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class QuoteData(BaseModel):
    symbol: str
    price: float
    change: Optional[float] = None
    change_percent: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    previous_close: Optional[float] = None
    volume: Optional[int] = None
    latest_trading_day: Optional[str] = None


class QuoteEnvelope(BaseModel):
    available: bool
    symbol: str
    provider: str = Field(default_factory=lambda: market_data.active_provider())
    source: str = Field(default_factory=lambda: market_data.active_provider())
    fetched_at: Optional[str] = None
    cached: bool = False
    reason: Optional[str] = None
    quote: Optional[QuoteData] = None


class WatchlistItem(BaseModel):
    symbol: str
    available: bool
    reason: Optional[str] = None
    quote: Optional[QuoteData] = None
    fetched_at: Optional[str] = None
    cached: bool = False


class WatchlistResponse(BaseModel):
    provider: str = Field(default_factory=lambda: market_data.active_provider())
    configured: bool
    items: List[WatchlistItem]


class SearchResult(BaseModel):
    symbol: str
    name: Optional[str] = None
    type: Optional[str] = None
    region: Optional[str] = None
    currency: Optional[str] = None


class SearchResponse(BaseModel):
    available: bool
    provider: str = Field(default_factory=lambda: market_data.active_provider())
    reason: Optional[str] = None
    results: List[SearchResult] = Field(default_factory=list)


class MarketStatusResponse(BaseModel):
    configured: bool
    provider: str = Field(default_factory=lambda: market_data.active_provider())
    cache_ttl_seconds: int
    watchlist_symbols: List[str]
    message: str


# ── AI watchlist insights ────────────────────────────────────────────────
# Short human labels for non-company symbols.
_WATCHLIST_NAMES = {
    "GC=F": "COMEX gold futures (front month)",
    "^GSPC": "S&P 500 index",
}


class InsightItem(BaseModel):
    symbol: str
    name: str
    price: float
    currency: Optional[str] = None
    day_change_percent: Optional[float] = None
    window_change_percent: Optional[float] = None
    window_days: Optional[int] = None
    volume: Optional[int] = None
    latest_trading_day: Optional[str] = None


class InsightsResponse(BaseModel):
    available: bool
    provider: str = Field(default_factory=lambda: market_data.active_provider())
    ai_generated: bool = False
    content: str = ""
    data: List[InsightItem] = Field(default_factory=list)
    generated_at: Optional[str] = None
    reason: Optional[str] = None


def _quote_model(payload: dict) -> QuoteData:
    return QuoteData(
        symbol=payload.get("symbol", ""),
        price=payload.get("price", 0.0),
        change=payload.get("change"),
        change_percent=payload.get("change_percent"),
        open=payload.get("open"),
        high=payload.get("high"),
        low=payload.get("low"),
        previous_close=payload.get("previous_close"),
        volume=payload.get("volume"),
        latest_trading_day=payload.get("latest_trading_day"),
    )


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("/status", response_model=MarketStatusResponse)
async def market_status(user: CurrentUser):
    """Report which market-data source is active (no secrets revealed)."""
    configured = market_data.is_configured()
    if configured:
        message = "Live quotes enabled via Alpha Vantage."
    elif market_data.active_provider() != "none":
        message = (
            "No Alpha Vantage key configured — quoting from Yahoo Finance "
            "(keyless source, 15-minute cache). Add ALPHA_VANTAGE_API_KEY for "
            "higher reliability."
        )
    else:
        message = (
            "No market-data API key configured. Quotes are unavailable rather "
            "than simulated."
        )
    return MarketStatusResponse(
        configured=configured,
        cache_ttl_seconds=settings.MARKET_DATA_CACHE_TTL_SECONDS,
        watchlist_symbols=market_data.DEFAULT_WATCHLIST,
        message=message,
    )


@router.get("/quotes/{symbol}", response_model=QuoteEnvelope)
async def get_stock_quote(
    symbol: str,
    user: CurrentUser,
    db: DbSession,
    force_refresh: bool = Query(False),
):
    """
    Fetch one quote.

    Returns ``available=false`` with a reason when the provider cannot supply
    data. It never returns an invented price.
    """
    try:
        normalized = market_data.normalize_symbol(symbol)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid ticker symbol",
        )

    try:
        payload = await market_data.get_quote(db, normalized, force_refresh=force_refresh)
    except market_data.MarketDataError as exc:
        return QuoteEnvelope(
            available=False, symbol=normalized, reason=str(exc)
        )

    if payload is None:
        return QuoteEnvelope(
            available=False,
            symbol=normalized,
            reason="Market data provider is not configured (set ALPHA_VANTAGE_API_KEY).",
        )

    return QuoteEnvelope(
        available=True,
        symbol=payload.get("symbol") or normalized,
        provider=payload.get("source", market_data.PROVIDER),
        source=payload.get("source", market_data.PROVIDER),
        fetched_at=payload.get("fetched_at"),
        cached=bool(payload.get("cached")),
        quote=_quote_model(payload),
    )


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(user: CurrentUser, db: DbSession):
    """Fetch the curated watchlist, marking each symbol's availability."""
    provider = market_data.active_provider()
    items: List[WatchlistItem] = []

    for symbol in market_data.DEFAULT_WATCHLIST:
        if provider == "none":
            items.append(
                WatchlistItem(
                    symbol=symbol,
                    available=False,
                    reason="Market data provider is not configured.",
                )
            )
            continue
        try:
            payload = await market_data.get_quote(db, symbol)
        except market_data.MarketDataError as exc:
            items.append(
                WatchlistItem(symbol=symbol, available=False, reason=str(exc))
            )
            continue
        if payload is None:
            items.append(
                WatchlistItem(
                    symbol=symbol,
                    available=False,
                    reason="Quote unavailable.",
                )
            )
            continue
        items.append(
            WatchlistItem(
                symbol=payload.get("symbol") or symbol,
                available=True,
                quote=_quote_model(payload),
                fetched_at=payload.get("fetched_at"),
                cached=bool(payload.get("cached")),
            )
        )

    return WatchlistResponse(configured=provider != "none", items=items)


@router.get("/search", response_model=SearchResponse)
async def search_symbols(
    user: CurrentUser,
    db: DbSession,
    q: str = Query(..., min_length=1, max_length=40),
):
    """Search ticker symbols. Returns an empty list when unconfigured."""
    if market_data.active_provider() == "none":
        return SearchResponse(
            available=False,
            reason="Market data provider is not configured.",
        )
    try:
        matches = await market_data.search_symbols(db, q)
    except market_data.MarketDataError as exc:
        return SearchResponse(available=False, reason=str(exc))

    return SearchResponse(
        available=True,
        results=[SearchResult(**match) for match in matches],
    )


def _insight_item(payload: dict) -> InsightItem:
    history = payload.get("history") or []
    return InsightItem(
        symbol=payload.get("symbol", ""),
        name=_WATCHLIST_NAMES.get(payload.get("symbol", ""), payload.get("symbol", "")),
        price=payload.get("price", 0.0),
        currency=payload.get("currency"),
        day_change_percent=payload.get("change_percent"),
        window_change_percent=payload.get("window_change_percent"),
        window_days=len(history) if history else None,
        volume=payload.get("volume") or None,
        latest_trading_day=payload.get("latest_trading_day"),
    )


def _deterministic_insights(items: List[InsightItem]) -> str:
    """Grounded, backend-computed trend summary (no model, no inventions)."""
    lines = []
    for item in items:
        parts: List[str] = [f"-> {item.symbol}: price {item.price}"]
        if item.currency:
            parts.append(f"{item.currency}")
        if item.day_change_percent is not None:
            parts.append(f"{item.day_change_percent:+.2f}% today")
        if (
            item.window_change_percent is not None
            and item.window_days
            and item.window_days >= 2
        ):
            parts.append(f"{item.window_change_percent:+.2f}% over {item.window_days} sessions")
        lines.append(" — ".join(parts) + ".")
    body = "\n".join(lines) if lines else "No fresh quotes are cached yet."
    return (
        "The AI model is unavailable right now, so here is a direct, "
        "computed trend summary instead:\n\n" + body + "\n\n"
        "Informational only - not investment advice."
    )


@router.get("/insights", response_model=InsightsResponse)
async def investment_insights(user: CurrentUser, db: DbSession):
    """
    Short per-symbol commentary for the default watchlist.

    The commentary is grounded: the model may only reference quote numbers
    that the backend fetched and displays. When Gemini is unavailable the
    endpoint falls back to a deterministic trend summary and flags it with
    ``ai_generated=false``.
    """
    if market_data.active_provider() == "none":
        return InsightsResponse(
            available=False, reason="Market data provider is not configured."
        )

    items: List[InsightItem] = []
    for symbol in market_data.DEFAULT_WATCHLIST:
        try:
            payload = await market_data.get_quote(db, symbol)
        except market_data.MarketDataError:
            continue
        if payload:
            items.append(_insight_item(payload))

    if not items:
        return InsightsResponse(
            available=False,
            reason="No fresh quotes are cached yet — press Refresh all first.",
        )

    data_block = "\n".join(
        f"{i.symbol} | {i.name} | price {i.price} {i.currency or ''}".rstrip()
        + (
            f" | latest day {i.day_change_percent:+.2f}%"
            if i.day_change_percent is not None
            else ""
        )
        + (
            f" | {i.window_change_percent:+.2f}% over {i.window_days} sessions"
            if i.window_change_percent is not None and i.window_days
            else ""
        )
        + (
            f" | volume {i.volume}"
            if i.volume
            else ""
        )
        for i in items
    )

    try:
        content = await gemini.generate_reply(
            system_prompt=gemini.build_insights_prompt(data_block),
            message=(
                "Write the watchlist commentary exactly as instructed: one "
                "grounded line per symbol, then the single warning line."
            ),
            temperature=0.3,
        )
        ai_generated = True
    except gemini.GeminiUnavailable:
        content = _deterministic_insights(items)
        ai_generated = False

    return InsightsResponse(
        available=True,
        ai_generated=ai_generated,
        content=content,
        data=items,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
