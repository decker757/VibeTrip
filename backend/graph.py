"""Small, serializable LangGraph workflow for a VibeTrip draft plan.

The nodes are deliberately provider-agnostic for the MVP. Real route, maps,
weather, and recommendation providers can be added behind each node without
changing the API contract or the frontend's state model.
"""

from datetime import datetime, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class PlannerState(TypedDict, total=False):
    start: str
    destination: str
    travellers: int
    budget_per_person: int
    dates: str
    start_date: str
    end_date: str
    start_time: str
    end_time: str
    preferences: list[str]
    adventure_level: int
    route_mode: str
    route: dict[str, Any]
    vibe_profile: dict[str, Any]
    candidate_places: list[dict[str, Any]]
    selected_places: list[dict[str, Any]]
    detours: list[dict[str, Any]]
    itinerary: list[dict[str, Any]]
    confidence: int


def _is_refuel_or_convenience(place: dict[str, Any]) -> bool:
    category = place.get("category", "").lower()
    return any(term in category for term in ("gas", "fuel", "convenience", "store"))


def _is_practical_stop(place: dict[str, Any]) -> bool:
    category = place.get("category", "").lower()
    return _is_refuel_or_convenience(place) or any(term in category for term in ("cafe", "coffee"))


def _practical_stop_title(place: dict[str, Any] | None) -> str:
    category = (place or {}).get("category", "").lower()
    if "convenience" in category or "store" in category:
        return "Snack + convenience"
    return "Fuel + bathroom"


def route_scout(state: PlannerState) -> PlannerState:
    """Find a practical baseline route and leave room for future map APIs."""
    route = state.get("route") or {
        "distance_km": 348,
        "drive_minutes": 229,
        "summary": f"{state['start']} to {state['destination']}",
        "stops_needed": ["fuel", "bathroom", "meal"],
    }
    return {
        **state,
        "route": route,
    }


def vibe_matcher(state: PlannerState) -> PlannerState:
    """Infer a lightweight archetype from the user's explicit preferences."""
    preferences = set(state.get("preferences", []))
    configured_level = state.get("adventure_level")
    adventure_score = int(configured_level) if configured_level is not None else (70 if "adventurous" in preferences or "local-gems" in preferences else 48)
    return {
        **state,
        "vibe_profile": {
            "archetype": "Curious, not rushed" if adventure_score >= 70 else "Easygoing explorer" if adventure_score <= 35 else "Balanced explorer",
            "adventure_score": adventure_score,
            "budget_mode": "student-friendly",
            "buffer_percent": 20,
        },
    }


def detour_reviewer(state: PlannerState) -> PlannerState:
    """Score candidate stops against time, budget, and the inferred profile."""
    candidates = state.get("candidate_places") or [{
        "id": "fallback-lunch",
        "name": "The Lobster Shack",
        "address": "Mystic, CT",
        "category": "Restaurant",
        "detour_minutes": 12,
        "enjoyment_score": 88,
        "reason": "A high-value meal stop with a short route deviation.",
        "open_now": True,
    }]
    ranked = sorted(candidates, key=lambda item: item.get("enjoyment_score", 0), reverse=True)
    route_mode = state.get("route_mode", "balanced")
    available = [item for item in ranked if item.get("open_now", True)]
    along_route = [item for item in available if item.get("recommendation_scope", "along_route") == "along_route"]
    meal = next((item for item in along_route if "restaurant" in item.get("category", "").lower()), None)
    scenic = next((item for item in along_route if item.get("recommendation_kind") == "scenic"), None)
    practical = next((item for item in along_route if _is_practical_stop(item)), None)
    selected: list[dict[str, Any]] = []

    def add_unique(place: dict[str, Any] | None) -> None:
        if place and place not in selected:
            selected.append(place)

    if route_mode == "fastest":
        add_unique(meal or practical or (available[0] if available else None))
    elif route_mode == "scenic":
        add_unique(scenic)
        add_unique(meal)
        add_unique(practical)
    else:
        add_unique(meal)
        add_unique(scenic)
        add_unique(practical)
    for place in available:
        if len(selected) >= {"fastest": 1, "balanced": 2, "scenic": 3}.get(route_mode, 2):
            break
        add_unique(place)
    return {**state, "candidate_places": ranked, "selected_places": selected, "detours": selected}


def day_builder(state: PlannerState) -> PlannerState:
    """Turn the route and accepted detours into a buffer-aware day plan."""
    route_mode = state.get("route_mode", "balanced")
    all_candidates = state.get("candidate_places", [])
    selected_candidates = state.get("selected_places", [])
    meal_stop = next((item for item in selected_candidates if "restaurant" in item.get("category", "").lower()), None)
    meal_stop = meal_stop or next((item for item in all_candidates if "restaurant" in item.get("category", "").lower() and item.get("open_now", True)), None)
    meal_name = meal_stop.get("name", "Lunch with a view") if meal_stop else "Lunch with a view"
    coffee_stop = next((item for item in all_candidates if item.get("recommendation_scope", "along_route") == "along_route" and any(term in item.get("category", "").lower() for term in ("cafe", "coffee")) and item.get("open_now", True)), None)
    practical_stops = sorted(
        (
            item for item in all_candidates
            if item.get("recommendation_scope", "along_route") == "along_route"
            and _is_refuel_or_convenience(item)
            and item.get("open_now", True)
        ),
        key=lambda item: (item.get("detour_minutes", 999), -item.get("enjoyment_score", 0)),
    )
    fuel_stop = practical_stops[0] if practical_stops else None
    additional_fuel_stop = practical_stops[1] if len(practical_stops) > 1 else None
    scenic_stop = next((item for item in selected_candidates if item.get("recommendation_kind") == "scenic" and item.get("recommendation_scope") == "along_route"), None)
    scenic_stop = scenic_stop or next((item for item in all_candidates if item.get("recommendation_kind") == "scenic" and item.get("recommendation_scope") == "along_route" and item.get("open_now", True)), None)
    route = dict(state.get("route") or {})
    drive_minutes = max(0, int(route.get("drive_minutes") or 229))
    try:
        start = datetime.strptime(state.get("start_time", "08:10"), "%H:%M")
    except ValueError:
        start = datetime.strptime("08:10", "%H:%M")

    def time_after(minutes: int) -> str:
        return (start + timedelta(minutes=minutes)).strftime("%H:%M")

    itinerary: list[dict[str, Any]] = []
    elapsed = 0
    planned_stop_minutes = 0
    if coffee_stop:
        # A place-based stop cannot happen at departure. Give the driver a
        # meaningful first driving leg before scheduling coffee or snacks.
        coffee_offset = max(60, round(drive_minutes * 0.22))
        itinerary.append({"time": time_after(coffee_offset), "title": "Coffee stop", "kind": "coffee", "duration_min": 25, "place_id": coffee_stop.get("id")})
        elapsed = coffee_offset + 25
        planned_stop_minutes += 25
    if drive_minutes >= 150 and fuel_stop:
        fuel_offset = max(elapsed + 75, round(drive_minutes * 0.45))
        itinerary.append({"time": time_after(fuel_offset), "title": _practical_stop_title(fuel_stop), "kind": "fuel", "duration_min": 15, "place_id": fuel_stop.get("id") if fuel_stop else None})
        elapsed = fuel_offset + 15
        planned_stop_minutes += 15
    if route_mode in {"balanced", "scenic"} and scenic_stop and drive_minutes >= 180:
        scenic_duration = 60 if route_mode == "scenic" else 45
        scenic_offset = max(elapsed + 35, min(drive_minutes - 120, 180))
        itinerary.append({"time": time_after(scenic_offset), "title": scenic_stop.get("name", "Scenic stop"), "kind": "attraction", "duration_min": scenic_duration, "place_id": scenic_stop.get("id")})
        elapsed = scenic_offset + scenic_duration
        planned_stop_minutes += scenic_duration
    if drive_minutes >= 360 and additional_fuel_stop:
        second_fuel_offset = max(elapsed + 60, round(drive_minutes * 0.62))
        itinerary.append({"time": time_after(second_fuel_offset), "title": _practical_stop_title(additional_fuel_stop), "kind": "fuel", "duration_min": 15, "place_id": additional_fuel_stop.get("id")})
        elapsed = second_fuel_offset + 15
        planned_stop_minutes += 15
    if drive_minutes >= 210:
        meal_offset = max(elapsed + 45, min(drive_minutes - 35, 260))
        itinerary.append({"time": time_after(meal_offset), "title": meal_name, "kind": "meal", "duration_min": 55, "place_id": meal_stop.get("id") if meal_stop else None})
        elapsed = meal_offset + 55
        planned_stop_minutes += 55
    buffer_minutes = max(20, round(drive_minutes * 0.2))
    arrival_offset = drive_minutes + planned_stop_minutes + buffer_minutes
    route.update({
        "buffer_minutes": buffer_minutes,
        "estimated_arrival_time": time_after(arrival_offset),
        "timeline_note": f"Includes a {buffer_minutes}-minute driving buffer plus planned breaks.",
        "stop_count": len(itinerary),
        "route_mode": route_mode,
        "route_mode_summary": {
            "fastest": "Essential breaks only; recommendations stay close to the route.",
            "balanced": "One worthwhile intermediate stop can break up the drive.",
            "scenic": "Scenic places and intermediate-city detours are allowed to shape the day.",
        }.get(route_mode, "Balanced route recommendations."),
    })
    try:
        end_time = datetime.strptime(state.get("end_time", "18:00"), "%H:%M")
        schedule_warning = None if start + timedelta(minutes=arrival_offset) <= end_time else f"Arrival estimate {time_after(arrival_offset)} is later than your target end time of {state.get('end_time', '18:00')}."
    except ValueError:
        schedule_warning = None
    route["schedule_warning"] = schedule_warning

    return {
        **state,
        "route": route,
        "confidence": 94,
        "itinerary": itinerary + [{"time": time_after(arrival_offset), "title": "Check-in", "kind": "stay", "duration_min": 0}],
    }


def build_planner_graph():
    """Compile the workflow once at application startup."""
    workflow = StateGraph(PlannerState)
    workflow.add_node("route_scout", route_scout)
    workflow.add_node("vibe_matcher", vibe_matcher)
    workflow.add_node("detour_reviewer", detour_reviewer)
    workflow.add_node("day_builder", day_builder)
    workflow.add_edge(START, "route_scout")
    workflow.add_edge("route_scout", "vibe_matcher")
    workflow.add_edge("vibe_matcher", "detour_reviewer")
    workflow.add_edge("detour_reviewer", "day_builder")
    workflow.add_edge("day_builder", END)
    return workflow.compile()


planner_graph = build_planner_graph()
