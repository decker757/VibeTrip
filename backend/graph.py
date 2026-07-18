"""Small, serializable LangGraph workflow for a VibeTrip draft plan.

The nodes are deliberately provider-agnostic for the MVP. Real route, maps,
weather, and recommendation providers can be added behind each node without
changing the API contract or the frontend's state model.
"""

from datetime import date, datetime, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .recommender import refine_recommendations


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
    recommendation_source: str
    recommendation_confidence: int
    recommendation_explanation: str
    profile_okf: str
    agent_context: dict[str, Any]
    context_summary: dict[str, Any]
    learned_preferences: list[str]


def _normalise_category(place: dict[str, Any]) -> str:
    return str(place.get("category") or "").lower()


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


def _opening_period_minutes(period_point: dict[str, Any] | None) -> int | None:
    if not period_point or period_point.get("day") is None:
        return None
    day = int(period_point.get("day", 0)) % 7
    hour = int(period_point.get("hour", 0))
    minute = int(period_point.get("minute", 0))
    return day * 24 * 60 + hour * 60 + minute


def _opening_status_at(place: dict[str, Any], arrival: datetime) -> bool | None:
    """Return scheduled opening status, or None when Google has no periods."""
    periods = (place.get("opening_hours") or {}).get("periods") or []
    if not periods:
        return None
    target = ((arrival.weekday() + 1) % 7) * 24 * 60 + arrival.hour * 60 + arrival.minute
    week = 7 * 24 * 60
    for period in periods:
        opened = _opening_period_minutes(period.get("open"))
        if opened is None:
            continue
        closed = _opening_period_minutes(period.get("close"))
        if closed is None:
            return True
        if closed <= opened:
            closed += week
        for offset in (-week, 0, week):
            if opened + offset <= target < closed + offset:
                return True
    return False


def _candidate_is_plannable(place: dict[str, Any]) -> bool:
    """Use regular hours when available; open_now is only a fallback."""
    return bool(place.get("opening_hours", {}).get("periods")) or place.get("open_now", True)


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
    context = state.get("agent_context", {})
    learned_preferences = set(context.get("learned_preferences", []))
    configured_level = state.get("adventure_level")
    adventure_score = int(configured_level) if configured_level is not None else (70 if "adventurous" in preferences or "local-gems" in preferences else 48)
    if "scenic_views" in learned_preferences:
        adventure_score = min(100, adventure_score + 5)
    if "quiet_low_crowd_stops" in learned_preferences:
        adventure_score = max(0, adventure_score - 3)
    return {
        **state,
        "learned_preferences": sorted(learned_preferences),
        "vibe_profile": {
            "archetype": "Curious, not rushed" if adventure_score >= 70 else "Easygoing explorer" if adventure_score <= 35 else "Balanced explorer",
            "adventure_score": adventure_score,
            "budget_mode": "student-friendly",
            "buffer_percent": 20,
            "learned_preferences": sorted(learned_preferences),
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
    route_mode = state.get("route_mode", "balanced")
    adventure_level = int(state.get("adventure_level") or 50)
    learned_preferences = set(state.get("agent_context", {}).get("learned_preferences", []))

    def recommendation_score(item: dict[str, Any]) -> float:
        """Use the profile to rank choices without changing route geometry."""
        enjoyment = float(item.get("enjoyment_score", 0))
        detour = float(item.get("detour_minutes", 0))
        scenic_bonus = 8 if item.get("recommendation_kind") == "scenic" else 0
        adventure_weight = adventure_level / 100
        detour_cost = detour * (1.3 - adventure_weight * 0.8)
        if route_mode == "fastest":
            detour_cost *= 1.5
        elif route_mode == "scenic":
            scenic_bonus *= 2
        learned_bonus = 0.0
        category = _normalise_category(item)
        crowd_risk = item.get("crowd_risk", "medium")
        if "quiet_low_crowd_stops" in learned_preferences:
            learned_bonus += 9 if crowd_risk in {"low", "medium"} else -9
        if "local_food" in learned_preferences and any(term in category for term in ("restaurant", "cafe", "food")):
            learned_bonus += 8
        if "scenic_views" in learned_preferences and item.get("recommendation_kind") == "scenic":
            learned_bonus += 8
        if "budget_conscious" in learned_preferences:
            price_level = item.get("price_level")
            if price_level is not None and int(price_level) <= 2:
                learned_bonus += 5
        return enjoyment + scenic_bonus * adventure_weight + learned_bonus - detour_cost

    ranked = sorted(candidates, key=recommendation_score, reverse=True)
    available = [item for item in ranked if _candidate_is_plannable(item)]
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
    return {
        **state,
        "candidate_places": ranked,
        "selected_places": selected,
        "detours": selected,
        "vibe_profile": {
            **state.get("vibe_profile", {}),
            "route_mode": route_mode,
            "recommendation_note": f"{route_mode.title()} controls the route shape; a {adventure_level}% adventure profile controls which stops win the tie-break.",
        },
    }


def day_builder(state: PlannerState) -> PlannerState:
    """Turn the route and accepted detours into a buffer-aware day plan."""
    route_mode = state.get("route_mode", "balanced")
    all_candidates = state.get("candidate_places", [])
    selected_candidates = state.get("selected_places", [])
    meal_stop = next((item for item in selected_candidates if "restaurant" in item.get("category", "").lower()), None)
    meal_stop = meal_stop or next((item for item in all_candidates if "restaurant" in item.get("category", "").lower() and _candidate_is_plannable(item)), None)
    meal_name = meal_stop.get("name", "Lunch with a view") if meal_stop else "Lunch with a view"
    coffee_stop = next((item for item in all_candidates if item.get("recommendation_scope", "along_route") == "along_route" and any(term in item.get("category", "").lower() for term in ("cafe", "coffee")) and _candidate_is_plannable(item)), None)
    practical_stops = sorted(
        (
            item for item in all_candidates
            if item.get("recommendation_scope", "along_route") == "along_route"
            and _is_refuel_or_convenience(item)
            and _candidate_is_plannable(item)
        ),
        key=lambda item: (item.get("detour_minutes", 999), -item.get("enjoyment_score", 0)),
    )
    fuel_stop = practical_stops[0] if practical_stops else None
    additional_fuel_stop = practical_stops[1] if len(practical_stops) > 1 else None
    scenic_stop = next((item for item in selected_candidates if item.get("recommendation_kind") == "scenic" and item.get("recommendation_scope") == "along_route"), None)
    scenic_stop = scenic_stop or next((item for item in all_candidates if item.get("recommendation_kind") == "scenic" and item.get("recommendation_scope") == "along_route" and _candidate_is_plannable(item)), None)
    route = dict(state.get("route") or {})
    drive_minutes = max(0, int(route.get("drive_minutes") or 229))
    today = date.today()
    try:
        trip_date = datetime.strptime(state.get("start_date", today.isoformat()), "%Y-%m-%d").date()
    except ValueError:
        trip_date = today
    try:
        start = datetime.combine(trip_date, datetime.strptime(state.get("start_time", "08:10"), "%H:%M").time())
    except ValueError:
        start = datetime.combine(trip_date, datetime.strptime("08:10", "%H:%M").time())

    def time_after(minutes: int) -> str:
        return (start + timedelta(minutes=minutes)).strftime("%H:%M")

    distance_km = max(1.0, float(route.get("distance_km") or 348))

    meal_options = []
    for candidate in [meal_stop, *all_candidates]:
        if candidate and "restaurant" in candidate.get("category", "").lower() and candidate not in meal_options and _candidate_is_plannable(candidate):
            meal_options.append(candidate)

    def build_planned_stops(selected_meal: dict[str, Any] | None) -> list[tuple[dict[str, Any], str, int]]:
        planned_stops: list[tuple[dict[str, Any], str, int]] = []
        seen_stop_ids: set[str] = set()

        def add_planned_stop(place: dict[str, Any] | None, kind: str, duration: int) -> None:
            if not place:
                return
            place_id = str(place.get("id") or place.get("name"))
            if place_id in seen_stop_ids:
                return
            seen_stop_ids.add(place_id)
            planned_stops.append((place, kind, duration))

        add_planned_stop(coffee_stop, "coffee", 25)
        add_planned_stop(fuel_stop, "fuel", 15)
        if route_mode in {"balanced", "scenic"} and drive_minutes >= 180:
            add_planned_stop(scenic_stop, "attraction", 60 if route_mode == "scenic" else 45)
        if drive_minutes >= 360:
            add_planned_stop(additional_fuel_stop, "fuel", 15)
        if drive_minutes >= 210:
            add_planned_stop(selected_meal, "meal", 55)
        planned_stops.sort(key=route_position)
        return planned_stops

    def route_position(item: tuple[dict[str, Any], str, int]) -> float:
        progress = item[0].get("route_progress_km")
        return float(progress) if isinstance(progress, (int, float)) else float("inf")

    def schedule_stops(planned_stops: list[tuple[dict[str, Any], str, int]]) -> tuple[list[dict[str, Any]], bool]:
        itinerary: list[dict[str, Any]] = []
        elapsed = 0
        previous_drive_offset = 0
        planned_stop_minutes = 0
        meal_was_open = True
        for index, (place, kind, duration) in enumerate(planned_stops):
            progress = place.get("route_progress_km")
            if isinstance(progress, (int, float)):
                driving_offset = round(drive_minutes * max(0, min(float(progress), distance_km)) / distance_km)
            else:
                driving_offset = round(drive_minutes * (index + 1) / (len(planned_stops) + 1))
            # A physical stop cannot happen at departure. Keep a minimum first
            # leg, then preserve geographic order for every later waypoint.
            driving_offset = max(60 if index == 0 else previous_drive_offset + 25, driving_offset)
            stop_offset = max(elapsed, driving_offset + planned_stop_minutes)
            opening_status = _opening_status_at(place, start + timedelta(minutes=stop_offset))
            if opening_status is False:
                if kind == "meal":
                    meal_was_open = False
                continue
            title = "Coffee stop" if kind == "coffee" else _practical_stop_title(place) if kind == "fuel" else place.get("name", "Lunch with a view") if kind == "meal" else place.get("name", "Scenic stop")
            itinerary.append({"time": time_after(stop_offset), "title": title, "kind": kind, "duration_min": duration, "place_id": place.get("id"), "route_progress_km": progress, "opening_hours_verified": opening_status is not None})
            elapsed = stop_offset + duration
            previous_drive_offset = driving_offset
            planned_stop_minutes += duration
        return itinerary, meal_was_open

    itinerary = []
    for option in [*meal_options, None]:
        candidate_itinerary, meal_was_open = schedule_stops(build_planned_stops(option))
        if option is None or meal_was_open:
            itinerary = candidate_itinerary
            meal_stop = option
            break
    buffer_minutes = max(20, round(drive_minutes * 0.2))
    planned_stop_minutes = sum(int(item.get("duration_min") or 0) for item in itinerary)
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
        "profile_influence_note": f"Route shape: {route_mode.title()}. Stop ranking: {int(state.get('adventure_level') or 50)}% adventurous.",
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
    workflow.add_node("llm_reviewer", refine_recommendations)
    workflow.add_node("day_builder", day_builder)
    workflow.add_edge(START, "route_scout")
    workflow.add_edge("route_scout", "vibe_matcher")
    workflow.add_edge("vibe_matcher", "detour_reviewer")
    workflow.add_edge("detour_reviewer", "llm_reviewer")
    workflow.add_edge("llm_reviewer", "day_builder")
    workflow.add_edge("day_builder", END)
    return workflow.compile()


planner_graph = build_planner_graph()
