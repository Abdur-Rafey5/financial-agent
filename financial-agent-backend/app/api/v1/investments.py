"""
Investments and market-data API.

All quotes come from Alpha Vantage through :mod:`app.services.market_data`.
When the provider is not configured, or rate-limits the request, the response
says so explicitly. Prices are never fabricated or extrapolated.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import settings
from app.services import market_data

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
    provider: str = market_data.PROVIDER
    source: str = market_data.PROVIDER
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
    provider: str = market_data.PROVIDER
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
    provider: str = market_data.PROVIDER
    reason: Optional[str] = None
    results: List[SearchResult] = Field(default_factory=list)


class MarketStatusResponse(BaseModel):
    configured: bool
    provider: str = market_data.PROVIDER
    cache_ttl_seconds: int
    watchlist_symbols: List[str]
    message: str


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
    """Report whether live market data is configured (no secrets revealed)."""
    configured = market_data.is_configured()
    return MarketStatusResponse(
        configured=configured,
        cache_ttl_seconds=settings.MARKET_DATA_CACHE_TTL_SECONDS,
        watchlist_symbols=market_data.DEFAULT_WATCHLIST,
        message=(
            "Live quotes enabled via Alpha Vantage."
            if configured
            else "No market-data API key configured. Quotes are unavailable rather than simulated."
        ),
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
    configured = market_data.is_configured()
    items: List[WatchlistItem] = []

    for symbol in market_data.DEFAULT_WATCHLIST:
        if not configured:
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

    return WatchlistResponse(configured=configured, items=items)


@router.get("/search", response_model=SearchResponse)
async def search_symbols(
    user: CurrentUser,
    db: DbSession,
    q: str = Query(..., min_length=1, max_length=40),
):
    """Search ticker symbols. Returns an empty list when unconfigured."""
    if not market_data.is_configured():
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
