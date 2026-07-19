"""Structured natural-language parsing for the route replacement assistant.

The parser may use an LLM to turn a conversational request into a Maps query,
but it never decides whether a result is geographically safe. Providers still
enforce the explicit locality and selected checkpoint segment deterministically.
"""

from __future__ import annotations

from collections import deque
import json
import os
import re
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from .providers import _extract_location_hint, _normalize_place_search_query
from .recommender import get_chat_model, llm_enabled


class PlaceSearchIntent(BaseModel):
    maps_query: str = Field(min_length=3, max_length=160)
    category: Literal["restaurant", "cafe", "fuel", "scenic", "other"] = "other"
    location_hint: str | None = Field(default=None, max_length=80)


_intent_cache: dict[str, PlaceSearchIntent] = {}
_intent_request_window: deque[float] = deque()


def _llm_search_enabled() -> bool:
    return llm_enabled() and os.getenv("VIBETRIP_LLM_SEARCH_ENABLED", "true").lower() not in {"0", "false", "no"}


def _search_request_available() -> bool:
    now = time.monotonic()
    while _intent_request_window and now - _intent_request_window[0] >= 60:
        _intent_request_window.popleft()
    try:
        limit = max(1, int(os.getenv("VIBETRIP_LLM_SEARCH_MAX_PER_MINUTE", "10")))
    except ValueError:
        limit = 10
    if len(_intent_request_window) >= limit:
        return False
    _intent_request_window.append(now)
    return True


def _category_for_query(query: str) -> str:
    normalized = _normalize_place_search_query(query)
    if normalized == "restaurant" or normalized.endswith(" restaurant"):
        return "restaurant"
    if normalized == "cafe coffee":
        return "cafe"
    if normalized == "gas station convenience store":
        return "fuel"
    if normalized == "scenic attraction":
        return "scenic"
    return "other"


def _deterministic_intent(query: str) -> PlaceSearchIntent:
    location_hint = _extract_location_hint(query)
    normalized = _normalize_place_search_query(query)
    maps_query = f"{normalized} near {location_hint}" if location_hint else normalized
    return PlaceSearchIntent(
        maps_query=maps_query[:160],
        category=_category_for_query(query),
        location_hint=location_hint,
    )


def _explicit_location(location_hint: str | None, query: str) -> bool:
    if not location_hint:
        return False
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    return all(token in query_tokens for token in location_hint.split())


def _safe_llm_intent(decision: PlaceSearchIntent, fallback: PlaceSearchIntent, query: str) -> PlaceSearchIntent:
    """Keep only model output that is grounded in the user's words."""
    location_hint = decision.location_hint if _explicit_location(decision.location_hint, query) else fallback.location_hint
    maps_query = decision.maps_query.strip()
    if not maps_query:
        maps_query = fallback.maps_query
    if location_hint and location_hint.lower() not in maps_query.lower():
        maps_query = f"{maps_query} near {location_hint}"
    return PlaceSearchIntent(
        maps_query=maps_query[:160],
        category=decision.category,
        location_hint=location_hint,
    )


def parse_place_search_intent(query: str, route_context: dict[str, Any] | None = None) -> PlaceSearchIntent:
    """Parse a request with an LLM when enabled, otherwise use safe rules."""
    fallback = _deterministic_intent(query)
    if not _llm_search_enabled() or not _search_request_available():
        return fallback

    cache_key = json.dumps({"query": query.strip().lower(), "context": route_context or {}}, sort_keys=True)
    if cache_key in _intent_cache:
        return _intent_cache[cache_key]
    prompt = {
        "request": query,
        "current_route_context": route_context or {},
        "deterministic_fallback": fallback.model_dump(),
    }
    try:
        decision = get_chat_model().with_structured_output(PlaceSearchIntent).invoke([
            (
                "system",
                "You parse VibeTrip route replacement requests into a Google Places text query. "
                "Extract an explicit locality only when the user says near, nearer to, close to, around, in, or at. "
                "Do not invent a locality from the route context. Use the route context only to understand the selected leg. "
                "The Maps query should be concise and retain the requested category and explicit locality. "
                "Do not choose a place, coordinates, route segment, or waypoint; deterministic code handles those constraints.",
            ),
            ("human", json.dumps(prompt, ensure_ascii=False)),
        ])
        parsed = _safe_llm_intent(decision, fallback, query)
        _intent_cache[cache_key] = parsed
        if len(_intent_cache) > 128:
            _intent_cache.pop(next(iter(_intent_cache)))
        return parsed
    except Exception:
        return fallback
