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
    current_stop_index: int | None,
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
    if current_stop_index is not None and 0 <= current_stop_index < len(itinerary):
        current_item = itinerary[current_stop_index]
        updated_itinerary = [item for index, item in enumerate(itinerary) if index != current_stop_index]
    elif current_stop_id:
        current_item = next((item for item in itinerary if item.get("place_id") == current_stop_id), None)
        updated_itinerary = [item for item in itinerary if item.get("place_id") != current_stop_id]
    else:
        current_item = next((item for item in itinerary if item.get("title") == current_stop_title), None)
        updated_itinerary = [item for item in itinerary if item.get("title") != current_stop_title]
    if replacement:
        replacement_category = replacement.get("category", "").lower()
        replacement_kind = (
            "meal" if "restaurant" in replacement_category
            else "fuel" if any(term in replacement_category for term in ("gas", "fuel", "convenience", "store"))
            else "coffee"
        )
        updated_itinerary.append({
            "time": current_item.get("time", "13:05") if current_item else "13:05",
            "title": f"{replacement['name']} (backup)",
            "kind": replacement_kind,
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
