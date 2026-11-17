"""Build durable, agent-readable context from a user's profile and trip history.

The database remains the source of truth. This module derives a compact context
object that can be rendered as OKF and passed to the planner without requiring
a vector store for the MVP.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower()


def _trip_stops(trip: dict[str, Any]) -> list[str]:
    return [
        str(item.get("title") or "").strip()
        for item in trip.get("itinerary", [])
        if item.get("kind") != "stay" and item.get("title")
    ]


SIGNAL_ORDER = ("local_food", "quiet_low_crowd_stops", "scenic_views", "budget_conscious")
SIGNAL_LABELS = {
    "local_food": "local food",
    "quiet_low_crowd_stops": "quieter, lower-crowd stops",
    "scenic_views": "scenic views",
    "budget_conscious": "budget-conscious options",
}
PROFILE_PREFERENCE_SIGNALS = {
    "local-gems": "local_food",
    "slow-mornings": "quiet_low_crowd_stops",
    "adventurous": "scenic_views",
}
DISMISS_EVENT = "signal_dismissed"


def _feedback_signals(event: dict[str, Any]) -> list[str]:
    if event.get("event_type") == DISMISS_EVENT:
        return []
    data = event.get("data") or {}
    text = " ".join(
        _normalise(value)
        for value in (
            event.get("event_type"),
            event.get("reason"),
            event.get("query"),
            event.get("old_place"),
            event.get("new_place"),
            data.get("reason"),
            data.get("query"),
            data.get("old_place"),
            data.get("new_place"),
        )
    )
    signals = []
    if any(term in text for term in ("quiet", "low crowd", "crowded", "crowd")):
        signals.append("quiet_low_crowd_stops")
    if any(term in text for term in ("local food", "restaurant", "chinese", "japanese", "thai", "malay", "food")):
        signals.append("local_food")
    if any(term in text for term in ("scenic", "view", "nature", "park", "lookout")):
        signals.append("scenic_views")
    if any(term in text for term in ("budget", "cheap", "affordable", "under")):
        signals.append("budget_conscious")
    return signals


def _behaviour_evidence(events: list[dict[str, Any]]) -> Counter:
    """Count feedback per signal, ignoring evidence from before the latest dismissal."""
    dismissed_at: dict[str, str] = {}
    for event in events:
        if event.get("event_type") == DISMISS_EVENT:
            signal = str((event.get("data") or {}).get("signal") or "")
            dismissed_at[signal] = max(dismissed_at.get(signal, ""), str(event.get("created_at") or ""))
    return Counter(
        signal
        for event in events
        for signal in _feedback_signals(event)
        if str(event.get("created_at") or "") > dismissed_at.get(signal, "")
    )


def _learned_signals(explicit_preferences: list[str], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from_profile = {PROFILE_PREFERENCE_SIGNALS[item] for item in explicit_preferences if item in PROFILE_PREFERENCE_SIGNALS}
    evidence = _behaviour_evidence(events)
    signals = []
    for signal in SIGNAL_ORDER:
        in_profile, in_behaviour = signal in from_profile, evidence.get(signal, 0) > 0
        if not (in_profile or in_behaviour):
            continue
        signals.append({
            "signal": signal,
            "label": SIGNAL_LABELS[signal],
            "source": "both" if in_profile and in_behaviour else "profile" if in_profile else "behaviour",
            "evidence_count": evidence.get(signal, 0),
            "confidence": round(min(0.95, 0.55 + evidence.get(signal, 0) * 0.12), 2),
        })
    return signals


def build_user_context(
    profile: dict[str, Any],
    trips: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a structured context snapshot for one authenticated user."""
    trips = trips or []
    events = events or []
    explicit_preferences = [str(item) for item in profile.get("preferences", []) if item]
    route_modes = Counter(str(trip.get("route_mode") or "balanced") for trip in trips)
    learned_signals = _learned_signals(explicit_preferences, events)
    learned_preferences = [item["signal"] for item in learned_signals]

    history = [
        {
            "id": trip.get("id"),
            "start": trip.get("start"),
            "destination": trip.get("destination"),
            "route_mode": trip.get("route_mode", "balanced"),
            "budget_per_person": trip.get("budget_per_person", 0),
            "completed": bool(trip.get("is_completed")),
            "public": bool(trip.get("is_public")),
            "preferences": [str(item) for item in trip.get("preferences", []) if item],
            "stops": _trip_stops(trip)[:8],
        }
        for trip in trips[-8:]
    ]
    recent_events = [
        {
            "event_type": event.get("event_type"),
            "trip_id": event.get("trip_id"),
            **dict(event.get("data") or {}),
            "created_at": event.get("created_at"),
        }
        for event in events[-20:]
    ]

    summary = {
        "trip_count": len(trips),
        "completed_trip_count": sum(1 for trip in trips if trip.get("is_completed")),
        "feedback_event_count": len(events),
        "learned_preferences": learned_preferences,
        "label": (
            f"Personalized using {len(trips)} saved {('trip' if len(trips) == 1 else 'trips')}"
            + (f" and {len(events)} {('feedback item' if len(events) == 1 else 'feedback items')}" if events else "")
        ),
        "signals_label": ", ".join(SIGNAL_LABELS[item] for item in learned_preferences),
    }

    return {
        "schema_version": "0.2",
        "profile": {
            "name": profile.get("name") or "VibeTrip traveller",
            "home_base": profile.get("home_base") or "Singapore",
            "exchange_student": bool(profile.get("exchange_student", True)),
            "preferences": explicit_preferences,
            "adventure_level": int(profile.get("adventure_level") or 50),
            "budget_per_person_sgd": int(profile.get("budget_per_person_sgd") or 0),
            "crowd_tolerance": profile.get("crowd_tolerance") or "medium",
            "pace": profile.get("pace") or "balanced",
        },
        "trip_history": history,
        "feedback_events": recent_events,
        "learned_preferences": learned_preferences,
        "learned_signals": learned_signals,
        "route_mode_history": dict(route_modes),
        "summary": summary,
        "agent_constraints": [
            "Use learned preferences only to rank feasible candidates.",
            "Keep route geometry, waypoint order, opening hours, and budget checks deterministic.",
            "Do not infer sensitive personal attributes from travel behaviour.",
        ],
    }
