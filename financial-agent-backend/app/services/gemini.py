"""
Google Gemini adapter.

The assistant only ever asks Gemini to *explain* facts that were already
computed deterministically by the backend. When no API key is configured, or
the provider fails, the caller receives a clear ``GeminiUnavailable`` error and
is expected to fall back to a deterministic, grounded summary.

We talk to the public Generative Language REST API directly so the service has
no additional SDK dependency and stays trivially mockable in tests.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiUnavailable(RuntimeError):
    """Raised when the Gemini API cannot be used for any reason."""


def is_configured() -> bool:
    """Whether a Gemini API key has been provided."""
    return bool(settings.GEMINI_API_KEY.strip())


async def generate_reply(
    *,
    system_prompt: str,
    message: str,
    history: Iterable[dict[str, str]] = (),
    temperature: float = 0.4,
) -> str:
    """
    Ask Gemini for a grounded natural-language answer.

    ``history`` items must look like ``{"role": "user"|"assistant", "content": str}``.
    Raises :class:`GeminiUnavailable` on missing configuration, transport
    failures, safety blocks, or empty responses.
    """
    if not is_configured():
        raise GeminiUnavailable("GEMINI_API_KEY is not configured")

    contents: list[dict] = []
    for item in history:
        role = "model" if item.get("role") == "assistant" else "user"
        text = (item.get("content") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 1024,
        },
    }

    url = f"{_API_ROOT}/{settings.GEMINI_MODEL}:generateContent"

    try:
        async with httpx.AsyncClient(timeout=settings.GEMINI_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json=payload,
            )
    except httpx.HTTPError as exc:  # network / timeout
        logger.warning("Gemini request failed: %s", exc)
        raise GeminiUnavailable("Gemini request failed") from exc

    if response.status_code >= 400:
        logger.warning("Gemini returned %s: %s", response.status_code, response.text[:500])
        raise GeminiUnavailable(f"Gemini returned HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise GeminiUnavailable("Gemini returned a non-JSON response") from exc

    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback") or {}
        raise GeminiUnavailable(
            f"Gemini returned no candidates ({feedback.get('blockReason', 'unknown reason')})"
        )

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise GeminiUnavailable("Gemini returned an empty response")
    return text


def build_system_prompt(context_block: str, currency: str) -> str:
    """System prompt enforcing the facts/estimates separation."""
    return (
        "You are an AI financial assistant embedded in a personal finance app.\n"
        "Rules you must never break:\n"
        "1. Only use the FINANCIAL SNAPSHOT below for numbers about the user. "
        "Never invent balances, transactions, prices or dates.\n"
        "2. Never perform arithmetic that is not already present in the snapshot. "
        "If a calculation is needed, show the formula and label the result as an estimate.\n"
        "3. Clearly separate facts (from the snapshot) from suggestions or estimates.\n"
        "4. Be concise (max ~180 words), practical and specific to the user's track "
        "(student, employee or businessman).\n"
        "5. If the snapshot lacks the data needed, say so and tell the user what to record.\n"
        f"6. Amounts are in {currency} unless stated otherwise. Format money without symbols.\n"
        "7. Do not give regulated investment, tax or legal advice; suggest a professional instead.\n\n"
        f"FINANCIAL SNAPSHOT\n{context_block}"
    )


def fallback_reply(question: str, context_block: str) -> str:
    """
    Deterministic, grounded answer used when Gemini is unavailable.

    It intentionally reports facts from the snapshot and never guesses.
    """
    return (
        "The AI language model is not available right now "
        "(no GEMINI_API_KEY configured or the provider is unreachable), "
        "so here is a direct summary computed by the backend:\n\n"
        f"{context_block}\n\n"
        "These figures are facts from your recorded data. "
        "Add a Gemini API key to receive conversational guidance about them."
    )


def build_insights_prompt(data_block: str) -> str:
    """System prompt for grounded per-symbol market commentary."""
    return (
        "You are the market-commentary module of a personal finance app.\n"
        "Rules you must never break:\n"
        "1. Use ONLY the MARKET DATA block for numbers. Never invent prices, "
        "percentages, history points or dates that are not printed there.\n"
        "2. Do not invent or reference news, events, earnings or macro reasons; "
        "you have not been given any such context.\n"
        "3. One short line (max ~30 words) per symbol, based strictly on the "
        "given recent-trend numbers: what the trend shows and what it could "
        "mean for someone considering buying — e.g. 'this can lead to a "
        "benefit if ...' followed by an 'if it falls below X there is a risk ...'.\n"
        "4. These are educational observations only; never promise returns.\n"
        "5. End with exactly: 'Informational only - not investment advice.'\n"
        "6. Plain text, one '->' bullet per symbol.\n\n"
        f"MARKET DATA\n{data_block}"
    )
