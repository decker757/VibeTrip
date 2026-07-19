"""Optional LLM ranking for already-validated route candidates.

The model is deliberately kept behind a narrow boundary: it may rank and
explain candidates, but it cannot create coordinates, prices, opening hours,
or route geometry. The deterministic reviewer remains the safe fallback.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field


class RecommendationDecision(BaseModel):
    """The only fields the LLM is allowed to return."""

    selected_place_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(default="")
    confidence: int = Field(default=0, ge=0, le=100)


def llm_enabled() -> bool:
    """Return whether an LLM is configured for this process."""
    return bool(os.getenv("OPENAI_API_KEY")) and os.getenv("VIBETRIP_LLM_ENABLED", "true").lower() not in {"0", "false", "no"}


@lru_cache(maxsize=1)
def get_chat_model() -> Any:
    """Create the model lazily so demo mode does not require the provider package."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.getenv("VIBETRIP_LLM_MODEL", "gpt-4o-mini"),
        temperature=0,
        timeout=float(os.getenv("VIBETRIP_LLM_TIMEOUT_SECONDS", "12")),
        max_retries=1,
    )


def _fallback_state(state: dict[str, Any], source: str = "deterministic") -> dict[str, Any]:
    return {
        **state,
        "recommendation_source": source,
        "recommendation_confidence": 0,
        "recommendation_explanation": "Hard constraints and deterministic route scoring selected these stops.",
    }


def refine_recommendations(state: dict[str, Any]) -> dict[str, Any]:
    """Use an LLM to rank a safe shortlist, with a deterministic fallback."""
    if not llm_enabled():
        return _fallback_state(state)

    route_mode = state.get("route_mode", "balanced")
    max_choices = {"fastest": 1, "balanced": 2, "scenic": 3}.get(route_mode, 2)
    candidates = [
        candidate
        for candidate in state.get("candidate_places", [])
        if candidate.get("recommendation_scope", "along_route") == "along_route"
        and candidate.get("open_now", True) is not False
    ][:10]
    if not candidates:
        return _fallback_state(state)

    prompt = {
        "trip": {
            "start": state.get("start"),
            "destination": state.get("destination"),
            "route_mode": route_mode,
            "travellers": state.get("travellers"),
            "budget_per_person_sgd": state.get("budget_per_person"),
            "start_time": state.get("start_time"),
            "end_time": state.get("end_time"),
            "preferences": state.get("preferences", []),
            "adventure_level": state.get("adventure_level", 50),
        },
        "profile_okf": state.get("profile_okf", ""),
        "learned_preferences": state.get("agent_context", {}).get("learned_preferences", []),
        "context_summary": state.get("context_summary", {}),
        "candidate_places": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "category": item.get("category"),
                "rating": item.get("rating"),
                "review_count": item.get("review_count"),
                "cost_label": item.get("cost_label") or item.get("price_label"),
                "detour_minutes": item.get("detour_minutes"),
                "enjoyment_score": item.get("enjoyment_score"),
                "crowd_risk": item.get("crowd_risk"),
                "route_progress_km": item.get("route_progress_km"),
                "recommendation_kind": item.get("recommendation_kind"),
                "reason": item.get("reason"),
            }
            for item in candidates
        ],
    }

    try:
        decision = get_chat_model().with_structured_output(RecommendationDecision).invoke([
            (
                "system",
                "You are VibeTrip's recommendation reviewer. Choose only IDs from the supplied candidate list. "
                f"Return at most {max_choices} IDs. Prefer a practical stop when the route mode is fastest, "
                "and balance memorable experiences with cost, crowd risk, detour time, and the user's profile. "
                "Use learned preferences as soft signals only; do not treat them as hard constraints. "
                "Do not invent facts. Coordinates, route order, opening hours, and final feasibility are handled "
                "by deterministic code. Keep the rationale to one concise sentence.",
            ),
            ("human", json.dumps(prompt, ensure_ascii=False)),
        ])
        allowed_ids = {str(item.get("id")) for item in candidates}
        selected_ids = [str(place_id) for place_id in decision.selected_place_ids if str(place_id) in allowed_ids][:max_choices]
        selected_places = [item for item in state.get("candidate_places", []) if str(item.get("id")) in selected_ids]
        if not selected_places:
            return _fallback_state(state)
        return {
            **state,
            "selected_places": selected_places,
            "detours": selected_places,
            "recommendation_source": "llm",
            "recommendation_confidence": int(decision.confidence),
            "recommendation_explanation": decision.rationale or "The recommendation model selected the best fit from the feasible shortlist.",
        }
    except Exception:
        # A failed model call must never prevent a valid route from being built.
        return _fallback_state(state, source="deterministic_fallback")
