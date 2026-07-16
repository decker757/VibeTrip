"""Mid-trip disruption handling for the simulation mode."""

from typing import Any, Literal


SimulationEvent = Literal["closed", "crowded", "running_late"]


def _is_eligible(candidate: dict[str, Any], event: SimulationEvent) -> bool:
    if not candidate.get("open_now", True):
        return False
    if event == "crowded" and candidate.get("crowd_risk") == "high":
        return False
    if event == "running_late" and candidate.get("detour_minutes", 0) > 8:
        return False
    return True


def recalibrate_trip(
    itinerary: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    current_stop_id: str | None,
    current_stop_title: str,
    event: SimulationEvent,
    destination: str,
) -> dict[str, Any]:
    """Choose the best remaining option, or go straight to the destination."""
    options = [
        candidate for candidate in candidates
        if candidate.get("id") != current_stop_id and _is_eligible(candidate, event)
    ]
    options.sort(key=lambda candidate: candidate.get("enjoyment_score", 0), reverse=True)
    replacement = options[0] if options else None
    updated_itinerary = [item for item in itinerary if item.get("title") != current_stop_title]
    if replacement:
        updated_itinerary.append({
            "time": "13:05",
            "title": f"{replacement['name']} (backup)",
            "kind": "meal" if "restaurant" in replacement.get("category", "").lower() else "coffee",
            "duration_min": 45,
            "place_id": replacement.get("id"),
        })
        updated_itinerary.sort(key=lambda item: item.get("time", ""))
        return {
            "action": "replace_stop",
            "replacement": replacement,
            "message": f"{current_stop_title} is {event.replace('_', ' ')}. I found {replacement['name']} instead — {replacement.get('detour_minutes', 0)} minutes off route.",
            "itinerary": updated_itinerary,
            "destination": destination,
        }
    updated_itinerary.append({"time": "now", "title": f"Head straight to {destination}", "kind": "stay", "duration_min": 0})
    return {
        "action": "go_to_destination",
        "replacement": None,
        "message": f"{current_stop_title} is unavailable and no safe replacement fits the remaining time. Continue to {destination}.",
        "itinerary": updated_itinerary,
        "destination": destination,
    }
