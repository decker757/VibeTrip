"""Small, serializable LangGraph workflow for a VibeTrip draft plan.

The nodes are deliberately provider-agnostic for the MVP. Real route, maps,
weather, and recommendation providers can be added behind each node without
changing the API contract or the frontend's state model.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import accumulate
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from .providers import DemoMapsProvider
from .opening_hours import candidate_is_plannable, opening_status_at
from .recommender import refine_recommendations
from .repair import finalize_best, repair_step, should_repair


class PlannerState(TypedDict, total=False):
    start: str
    destination: str
    travellers: int
    budget_per_person: int
    dates: str
    start_date: str
    end_date: str
    start_time: str
    end_time: str | None
    preferences: list[str]
    adventure_level: int
    route_mode: str
    crowd_tolerance: str
    provider_name: str
    provider_warning: str | None
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
    # Repair loop (see repair.py). Undeclared keys are dropped between nodes.
    skipped_stop_kinds: list[str]
    repair_attempts: int
    repair_settled: bool
    repair_unfixable: bool
    repair_snapshots: list[dict[str, Any]]
    repair_log: list[dict[str, Any]]
    make_room_mode: bool


def _normalise_category(place: dict[str, Any]) -> str:
    return str(place.get("category") or "").lower()


def _is_refuel_or_convenience(place: dict[str, Any]) -> bool:
    category = place.get("category", "").lower()
    return any(term in category for term in ("gas", "fuel", "convenience", "store"))


def _is_fuel_stop(place: dict[str, Any]) -> bool:
    category = place.get("category", "").lower()
    return any(term in category for term in ("gas", "fuel", "petrol"))


def _is_practical_stop(place: dict[str, Any]) -> bool:
    category = place.get("category", "").lower()
    return _is_refuel_or_convenience(place) or any(term in category for term in ("cafe", "coffee"))


def _practical_stop_title(place: dict[str, Any] | None) -> str:
    category = (place or {}).get("category", "").lower()
    if "convenience" in category or "store" in category:
        return "Snack + convenience"
    return "Fuel + bathroom"


async def route_scout(state: PlannerState, config: RunnableConfig | None = None) -> PlannerState:
    """Fetch the baseline route and candidate places from the injected maps provider.

    The provider arrives through ``config["configurable"]["maps_provider"]`` so
    tests can inject one. Without a provider the node keeps any route already in
    state (used by node-level tests and resumed drafts).
    """
    provider = ((config or {}).get("configurable") or {}).get("maps_provider")
    if provider is not None:
        args = (
            state["start"],
            state["destination"],
            int(state.get("budget_per_person") or 400),
            state.get("crowd_tolerance", "medium"),
            state.get("start_time", "08:10"),
            state.get("route_mode", "balanced"),
        )
        fallback_warning = None
        try:
            result = await provider.plan_trip(*args)
        except Exception as error:
            result = await DemoMapsProvider().plan_trip(*args)
            fallback_warning = f"Maps provider unavailable ({type(error).__name__}); showing demo candidates."
        return {
            **state,
            "route": result.route,
            "candidate_places": result.candidates,
            "provider_name": result.provider,
            "provider_warning": fallback_warning or result.warning,
        }
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
    available = [item for item in ranked if candidate_is_plannable(item)]
    along_route = [item for item in available if item.get("recommendation_scope", "along_route") == "along_route"]
    fuel = next((item for item in along_route if _is_fuel_stop(item)), None)
    meal = next((item for item in along_route if "restaurant" in item.get("category", "").lower()), None)
    scenic = next((item for item in along_route if item.get("recommendation_kind") == "scenic"), None)
    practical = next((item for item in along_route if _is_practical_stop(item)), None)
    selected: list[dict[str, Any]] = []

    def add_unique(place: dict[str, Any] | None) -> None:
        if place and place not in selected:
            selected.append(place)

    if route_mode == "fastest":
        add_unique(fuel or meal or practical or (available[0] if available else None))
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


COFFEE_MINUTES = 25
FUEL_MINUTES = 15
ATTRACTION_MINUTES = {"balanced": 45, "scenic": 60}
MEAL_MINUTES = 55
# Floors for stops with no route position, where the drive to them is only a guess.
FIRST_LEG_MIN_MINUTES = 60
MIN_LEG_GAP_MINUTES = 25
# Stops with a known position: even neighbouring places take a few minutes to leave and reach.
SHORT_HOP_MINUTES = 5
ATTRACTION_MIN_DRIVE = 180
MEAL_MIN_DRIVE = 210
SECOND_FUEL_MIN_DRIVE = 360
# Stop timing: choose fuel and lunch near where on the route they're needed.
FUEL_MIN_GAP_KM = 150
TARGET_WINDOW_RATIO = 0.15
LUNCH_TARGET = time(12, 30)
MEAL_TARGET_BOUNDS = (0.2, 0.8)
BUFFER_RATIO = 0.2
MIN_BUFFER_MINUTES = 20

PlannedStop = tuple[dict[str, Any], str, int]


@dataclass
class StopOptions:
    meal_stop: dict[str, Any] | None
    meal_options: list[dict[str, Any]]
    coffee_stop: dict[str, Any] | None
    fuel_stops: list[dict[str, Any]]
    fuel_stop: dict[str, Any] | None
    scenic_stop: dict[str, Any] | None
    second_fuel_target_km: float | None = None
    window_km: float = 0.0

    def second_fuel_after(self, first: dict[str, Any] | None) -> dict[str, Any] | None:
        """The fuel stop nearest the second target that is at least FUEL_MIN_GAP_KM past ``first``."""
        first_km = _progress_km(first) if first else None
        if self.second_fuel_target_km is None or first_km is None:
            return None
        spaced = [
            item for item in self.fuel_stops
            if item is not first and (_progress_km(item) or 0) - first_km >= FUEL_MIN_GAP_KM
        ]
        return next(iter(_order_near_target(spaced, self.second_fuel_target_km, self.window_km)), None)


@dataclass
class ScheduleResult:
    itinerary: list[dict[str, Any]]
    meal_was_open: bool
    fuel_was_scheduled: bool
    arrival_offset: int


@dataclass
class DriveClock:
    """Driving minutes from departure to any stop, with the buffer spread over every leg.

    Uses Google's per-leg times for stops the route was plotted through, otherwise the
    stop's share of the route distance.
    """

    drive_minutes: int
    distance_km: float
    buffer_minutes: int
    real_offsets: dict[str, int]

    def position(self, place: dict[str, Any], index: int, stop_count: int) -> tuple[float, bool]:
        """(driving minutes from departure, whether that position is known rather than guessed)."""
        real = self.real_offsets.get(str(place.get("id")))
        if real is not None:
            return float(real), True
        progress = place.get("route_progress_km")
        if isinstance(progress, (int, float)):
            return self.drive_minutes * max(0.0, min(float(progress), self.distance_km)) / self.distance_km, True
        return self.drive_minutes * (index + 1) / (stop_count + 1), False

    def with_buffer(self, driving: float) -> int:
        return round(driving * (1 + self.buffer_minutes / self.drive_minutes)) if self.drive_minutes else round(driving)


def _real_drive_offsets(route: dict[str, Any]) -> dict[str, int]:
    """Driving minutes to each routed waypoint, when Google returned one leg per waypoint plus the last."""
    waypoint_ids = route.get("routed_waypoint_ids") or []
    leg_minutes = route.get("leg_minutes") or []
    if not waypoint_ids or len(leg_minutes) != len(waypoint_ids) + 1:
        return {}
    return {str(place_id): offset for place_id, offset in zip(waypoint_ids, accumulate(leg_minutes))}


def _is_restaurant(place: dict[str, Any]) -> bool:
    return "restaurant" in place.get("category", "").lower()


def _is_along_route(place: dict[str, Any]) -> bool:
    return place.get("recommendation_scope", "along_route") == "along_route"


def _sorted_by_detour(places: Any) -> list[dict[str, Any]]:
    return sorted(places, key=lambda item: (item.get("detour_minutes", 999), -item.get("enjoyment_score", 0)))


def _progress_km(place: dict[str, Any]) -> float | None:
    value = place.get("route_progress_km")
    return float(value) if isinstance(value, (int, float)) else None


def _order_near_target(options: list[dict[str, Any]], target_km: float, window_km: float) -> list[dict[str, Any]]:
    """Ranked options inside the window around the target first (rank kept), then the rest by closeness."""
    def distance(place: dict[str, Any]) -> float:
        progress = _progress_km(place)
        return abs(progress - target_km) if progress is not None else float("inf")

    inside = [place for place in options if distance(place) <= window_km]
    outside = sorted((place for place in options if distance(place) > window_km), key=distance)
    return inside + outside


def _fuel_targets(distance_km: float, drive_minutes: int) -> list[float]:
    """Where on the route fuel is wanted: halfway, or at thirds on drives long enough for two stops."""
    if drive_minutes >= SECOND_FUEL_MIN_DRIVE:
        return [distance_km / 3, distance_km * 2 / 3]
    return [distance_km / 2]


def _meal_target_km(state: PlannerState, distance_km: float, drive_minutes: int) -> float:
    """The route km reached around lunchtime, kept off the ends of the route; midway if the drive misses lunch."""
    start = _parse_start(state)
    lunch = datetime.combine(start.date(), LUNCH_TARGET)
    minutes_to_lunch = (lunch - start).total_seconds() / 60
    if drive_minutes <= 0 or not 0 < minutes_to_lunch < drive_minutes:
        return distance_km / 2
    low, high = MEAL_TARGET_BOUNDS
    return min(max(minutes_to_lunch * distance_km / drive_minutes, distance_km * low), distance_km * high)


def _pick_stop_options(state: PlannerState) -> StopOptions:
    """Choose the candidate for each stop role from the ranked places, near where on the route it's needed."""
    route_mode = state.get("route_mode", "balanced")
    all_candidates = state.get("candidate_places", [])
    selected_candidates = state.get("selected_places", [])
    route = state.get("route") or {}
    distance_km = max(1.0, float(route.get("distance_km") or 348))
    drive_minutes = max(0, int(route.get("drive_minutes") or 229))
    window_km = distance_km * TARGET_WINDOW_RATIO
    fuel_targets = _fuel_targets(distance_km, drive_minutes)
    meal_stop = next((item for item in selected_candidates if _is_restaurant(item)), None)
    meal_stop = meal_stop or next((item for item in all_candidates if _is_restaurant(item) and candidate_is_plannable(item)), None)
    coffee_stop = next((item for item in all_candidates if _is_along_route(item) and any(term in item.get("category", "").lower() for term in ("cafe", "coffee")) and candidate_is_plannable(item)), None)
    fuel_stops = _order_near_target(_sorted_by_detour(item for item in all_candidates if _is_along_route(item) and _is_fuel_stop(item) and candidate_is_plannable(item)), fuel_targets[0], window_km)
    practical_stops = _order_near_target(_sorted_by_detour(item for item in all_candidates if _is_along_route(item) and _is_refuel_or_convenience(item) and candidate_is_plannable(item)), fuel_targets[0], window_km)
    fuel_stop = fuel_stops[0] if fuel_stops else practical_stops[0] if route_mode != "fastest" and practical_stops else None
    scenic_stop = next((item for item in selected_candidates if item.get("recommendation_kind") == "scenic" and item.get("recommendation_scope") == "along_route"), None)
    scenic_stop = scenic_stop or next((item for item in all_candidates if item.get("recommendation_kind") == "scenic" and item.get("recommendation_scope") == "along_route" and candidate_is_plannable(item)), None)
    meal_options: list[dict[str, Any]] = []
    for candidate in [meal_stop, *all_candidates]:
        if candidate and _is_restaurant(candidate) and candidate not in meal_options and candidate_is_plannable(candidate):
            meal_options.append(candidate)
    meal_options = _order_near_target(meal_options, _meal_target_km(state, distance_km, drive_minutes), window_km)
    return StopOptions(
        meal_stop=meal_options[0] if meal_options else meal_stop,
        meal_options=meal_options,
        coffee_stop=coffee_stop,
        fuel_stops=fuel_stops,
        fuel_stop=fuel_stop,
        second_fuel_target_km=fuel_targets[1] if len(fuel_targets) > 1 else None,
        window_km=window_km,
        scenic_stop=scenic_stop,
    )


def _route_position(item: PlannedStop) -> float:
    progress = item[0].get("route_progress_km")
    return float(progress) if isinstance(progress, (int, float)) else float("inf")


def _build_planned_stops(options: StopOptions, meal: dict[str, Any] | None, fuel: dict[str, Any] | None, route_mode: str, drive_minutes: int, skipped_kinds: frozenset[str] = frozenset()) -> list[PlannedStop]:
    """Assemble stops for one meal/fuel choice, ordered along the route.

    ``skipped_kinds`` may contain ``coffee``, ``attraction`` and ``extra_fuel``;
    the meal and the first fuel stop are never skippable.
    """
    planned_stops: list[PlannedStop] = []
    seen_stop_ids: set[str] = set()

    def add(place: dict[str, Any] | None, kind: str, duration: int) -> None:
        if not place:
            return
        place_id = str(place.get("id") or place.get("name"))
        if place_id in seen_stop_ids:
            return
        seen_stop_ids.add(place_id)
        planned_stops.append((place, kind, duration))

    if route_mode != "fastest" and "coffee" not in skipped_kinds:
        add(options.coffee_stop, "coffee", COFFEE_MINUTES)
    add(fuel, "fuel", FUEL_MINUTES)
    if route_mode in {"balanced", "scenic"} and drive_minutes >= ATTRACTION_MIN_DRIVE and "attraction" not in skipped_kinds:
        add(options.scenic_stop, "attraction", ATTRACTION_MINUTES[route_mode])
    if drive_minutes >= SECOND_FUEL_MIN_DRIVE and "extra_fuel" not in skipped_kinds:
        add(options.second_fuel_after(fuel), "fuel", FUEL_MINUTES)
    if drive_minutes >= MEAL_MIN_DRIVE:
        add(meal, "meal", MEAL_MINUTES)
    planned_stops.sort(key=_route_position)
    return planned_stops


def _schedule_metadata(start: datetime, minutes: int) -> dict[str, Any]:
    scheduled_at = start + timedelta(minutes=minutes)
    return {
        "time": scheduled_at.strftime("%H:%M"),
        "date": scheduled_at.date().isoformat(),
        "day_number": (scheduled_at.date() - start.date()).days + 1,
        "schedule_offset_minutes": minutes,
    }


def _schedule_stops(planned_stops: list[PlannedStop], start: datetime, clock: DriveClock) -> ScheduleResult:
    """Place stops on the timeline, dropping any that would arrive while closed.

    Each leg is that stretch of road's own driving time. A floor that lengthens a short
    leg adds time to the day; it is never taken back from a later leg.
    """
    itinerary: list[dict[str, Any]] = []
    driving = 0.0  # driving minutes to the last kept stop, floors included
    last_position = 0.0  # where that stop sits on the route, in driving minutes
    planned_stop_minutes = 0
    meal_was_open = True
    fuel_was_scheduled = False
    for index, (place, kind, duration) in enumerate(planned_stops):
        position, known = clock.position(place, index, len(planned_stops))
        floor = SHORT_HOP_MINUTES if known else MIN_LEG_GAP_MINUTES if itinerary else FIRST_LEG_MIN_MINUTES
        arrival_driving = driving + max(floor, position - last_position)
        stop_offset = clock.with_buffer(arrival_driving) + planned_stop_minutes
        opening_status = opening_status_at(place, start + timedelta(minutes=stop_offset))
        if opening_status is False:
            if kind == "meal":
                meal_was_open = False
            continue
        title = "Coffee stop" if kind == "coffee" else _practical_stop_title(place) if kind == "fuel" else place.get("name", "Lunch with a view") if kind == "meal" else place.get("name", "Scenic stop")
        itinerary.append({**_schedule_metadata(start, stop_offset), "title": title, "kind": kind, "duration_min": duration, "place_id": place.get("id"), "route_progress_km": place.get("route_progress_km"), "opening_hours_verified": opening_status is not None})
        driving = arrival_driving
        last_position = max(last_position, position)
        planned_stop_minutes += duration
        if kind == "fuel":
            fuel_was_scheduled = True
    arrival_driving = driving + max(0.0, clock.drive_minutes - last_position)
    return ScheduleResult(itinerary, meal_was_open, fuel_was_scheduled, clock.with_buffer(arrival_driving) + planned_stop_minutes)


def _schedule_warnings(state: PlannerState, start: datetime, arrival_offset: int, fuel_scheduled: bool) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if state.get("route_mode", "balanced") == "fastest" and not fuel_scheduled:
        warnings.append({"code": "fastest_no_fuel", "message": "Fastest routes require at least one fuel station, but no usable fuel stop could be scheduled. Try generating again or choose Balanced."})
    arrival = start + timedelta(minutes=arrival_offset)
    end_time = state.get("end_time")
    if end_time:
        try:
            target_end = datetime.combine(start.date(), datetime.strptime(end_time, "%H:%M").time())
            if arrival > target_end:
                warnings.append({"code": "late_arrival", "message": f"Arrival estimate {arrival.strftime('%H:%M')} is later than your target end time of {end_time}."})
        except ValueError:
            pass
    return warnings


def _parse_start(state: PlannerState) -> datetime:
    today = date.today()
    try:
        trip_date = datetime.strptime(state.get("start_date", today.isoformat()), "%Y-%m-%d").date()
    except ValueError:
        trip_date = today
    try:
        return datetime.combine(trip_date, datetime.strptime(state.get("start_time", "08:10"), "%H:%M").time())
    except ValueError:
        return datetime.combine(trip_date, datetime.strptime("08:10", "%H:%M").time())


def day_builder(state: PlannerState) -> PlannerState:
    """Turn the route and accepted detours into a buffer-aware day plan."""
    route_mode = state.get("route_mode", "balanced")
    options = _pick_stop_options(state)
    route = dict(state.get("route") or {})
    drive_minutes = max(0, int(route.get("drive_minutes") or 229))
    distance_km = max(1.0, float(route.get("distance_km") or 348))
    start = _parse_start(state)
    skipped_kinds = frozenset(state.get("skipped_stop_kinds", []))
    buffer_minutes = max(MIN_BUFFER_MINUTES, round(drive_minutes * BUFFER_RATIO))
    clock = DriveClock(drive_minutes, distance_km, buffer_minutes, _real_drive_offsets(route))

    itinerary: list[dict[str, Any]] = []
    arrival_offset = clock.with_buffer(drive_minutes)
    scheduled_fuel_stop = None
    if route_mode == "fastest":
        fuel_options = [*options.fuel_stops, None]
    else:
        fuel_options = [options.fuel_stop, *(item for item in options.fuel_stops if item is not options.fuel_stop)]
    for index, fuel_option in enumerate(fuel_options):
        is_last_fuel_option = index == len(fuel_options) - 1
        for meal_option in [*options.meal_options, None]:
            result = _schedule_stops(_build_planned_stops(options, meal_option, fuel_option, route_mode, drive_minutes, skipped_kinds), start, clock)
            # If this first fuel stop was dropped (closed on arrival), try the next station rather than
            # accepting a day whose only fuel is the far second stop.
            first_fuel_kept = fuel_option is None or is_last_fuel_option or any(
                item.get("place_id") == fuel_option.get("id") for item in result.itinerary
            )
            fuel_requirement_met = first_fuel_kept and (route_mode != "fastest" or result.fuel_was_scheduled)
            if fuel_requirement_met and (meal_option is None or result.meal_was_open):
                itinerary = result.itinerary
                arrival_offset = result.arrival_offset
                scheduled_fuel_stop = fuel_option if result.fuel_was_scheduled else None
                break
        if itinerary:
            break

    warnings = _schedule_warnings(state, start, arrival_offset, scheduled_fuel_stop is not None)
    arrival_metadata = _schedule_metadata(start, arrival_offset)
    route.update({
        "buffer_minutes": buffer_minutes,
        "estimated_arrival_time": arrival_metadata["time"],
        "estimated_arrival_date": arrival_metadata["date"],
        "estimated_trip_days": arrival_metadata["day_number"],
        "timeline_note": f"Includes a {buffer_minutes}-minute driving buffer plus planned breaks.",
        "stop_count": len(itinerary),
        "route_mode": route_mode,
        "route_mode_summary": {
            "fastest": "Essential breaks only, including at least one fuel stop; optional coffee and scenic detours are excluded.",
            "balanced": "One worthwhile intermediate stop can break up the drive.",
            "scenic": "Scenic places and intermediate-city detours are allowed to shape the day.",
        }.get(route_mode, "Balanced route recommendations."),
        "profile_influence_note": f"Route shape: {route_mode.title()}. Stop ranking: {int(state.get('adventure_level') or 50)}% adventurous.",
        "warnings": warnings,
        "arrival_offset_minutes": arrival_offset,
        "schedule_warning": " ".join(w["message"] for w in warnings) or None,
    })

    return {
        **state,
        "route": route,
        "confidence": 94,
        "itinerary": itinerary + [{**arrival_metadata, "title": "Check-in", "kind": "stay", "duration_min": 0}],
    }


def build_planner_graph():
    """Compile the workflow once at application startup."""
    workflow = StateGraph(PlannerState)
    workflow.add_node("route_scout", route_scout)
    workflow.add_node("vibe_matcher", vibe_matcher)
    workflow.add_node("detour_reviewer", detour_reviewer)
    workflow.add_node("llm_reviewer", refine_recommendations)
    workflow.add_node("day_builder", day_builder)
    workflow.add_node("repair", lambda s: repair_step(s, day_builder))
    workflow.add_node("finalize", finalize_best)
    workflow.add_edge(START, "route_scout")
    workflow.add_edge("route_scout", "vibe_matcher")
    workflow.add_edge("vibe_matcher", "detour_reviewer")
    workflow.add_edge("detour_reviewer", "llm_reviewer")
    workflow.add_edge("llm_reviewer", "day_builder")
    workflow.add_conditional_edges("day_builder", should_repair, {"repair": "repair", "finalize": "finalize"})
    workflow.add_edge("repair", "day_builder")
    workflow.add_edge("finalize", END)
    return workflow.compile()


planner_graph = build_planner_graph()
