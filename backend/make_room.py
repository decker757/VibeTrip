"""Make room for the destination: plan the drive around what the traveller wants to do there.

The deadline comes from the chosen place's opening hours, not from a clock time
the traveller has to guess. The planner then trims optional stops when the drive
runs late (repair.py in make-room mode), or offers one stop to fill spare time.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from .opening_hours import candidate_is_plannable
from .route_agent import RouteAgentContext, fits_spare, run_route_agent

VISIT_MINUTES_FOOD = 60
VISIT_MINUTES_DEFAULT = 90
FOOD_TERMS = ("restaurant", "cafe", "food", "bakery")
LAST_MINUTE_OF_DAY = time(23, 59)
FILL_TRIGGER_MINUTES = 45
# Learned signals in priority order, mapped to the fill query the agent starts from.
FILL_QUERIES = (
    ("scenic_views", "scenic viewpoint or nature stop"),
    ("local_food", "local food spot"),
    ("quiet_low_crowd_stops", "quiet low-crowd stop"),
)
DEFAULT_FILL_QUERY = "scenic stop or local attraction"
# Fill searches skip this share of the gap at each end, so the stop doesn't sit next to the start or another stop.
GAP_EDGE_MARGIN = 0.1


@dataclass
class Deadline:
    deadline: datetime
    closes_at: datetime
    visit_minutes: int


def visit_minutes(place: dict[str, Any]) -> int:
    category = str(place.get("category") or "").lower()
    return VISIT_MINUTES_FOOD if any(term in category for term in FOOD_TERMS) else VISIT_MINUTES_DEFAULT


def _windows_on(periods: list[dict[str, Any]], on: date) -> list[tuple[datetime, datetime]]:
    """(opens, closes) for each period that opens on ``on``; closes after midnight cap at 23:59."""
    google_day = (on.weekday() + 1) % 7  # Google counts days from Sunday = 0
    windows = []
    for period in periods:
        opened, closed = period.get("open") or {}, period["close"]
        if opened.get("day") != google_day:
            continue
        opens = datetime.combine(on, time(int(opened.get("hour", 0)), int(opened.get("minute", 0))))
        if closed.get("day") != google_day:
            closes = datetime.combine(on, LAST_MINUTE_OF_DAY)
        else:
            closes = datetime.combine(on, time(int(closed.get("hour", 0)), int(closed.get("minute", 0))))
        windows.append((opens, closes))
    return sorted(windows)


def destination_deadline(place: dict[str, Any], on: date, current_arrival: datetime | None) -> Deadline | None:
    """Latest arrival that still leaves time for the visit; None means no usable hours.

    With split hours, pick the earliest window still reachable at the current
    arrival; if none is, use the last one so the planner can try to trim.
    """
    periods = (place.get("opening_hours") or {}).get("periods") or []
    if not periods or any("close" not in period for period in periods):
        return None  # no hours on record, or open 24 hours
    windows = _windows_on(periods, on)
    if not windows:
        return None
    visit = visit_minutes(place)
    reachable = [w for w in windows if current_arrival is None or w[1] - timedelta(minutes=visit) >= current_arrival]
    _, closes = reachable[0] if reachable else windows[-1]
    return Deadline(deadline=closes - timedelta(minutes=visit), closes_at=closes, visit_minutes=visit)


# --- Filling spare time ---

def _progress(item: dict[str, Any]) -> float | None:
    value = item.get("route_progress_km")
    return float(value) if isinstance(value, (int, float)) else None


def longest_gap(itinerary: list[dict[str, Any]], distance_km: float) -> tuple[float, float]:
    """The longest stretch of road between consecutive stops, counting the start and the destination."""
    points = sorted({0.0, float(distance_km), *(p for p in map(_progress, itinerary) if p is not None)})
    return max(zip(points, points[1:]), key=lambda gap: gap[1] - gap[0])


def fill_query(learned_preferences: list[str]) -> str:
    return next((query for signal, query in FILL_QUERIES if signal in learned_preferences), DEFAULT_FILL_QUERY)


def deterministic_fill(candidates: list[dict[str, Any]], gap: tuple[float, float], used_ids: set[str], spare_minutes: int) -> dict[str, Any] | None:
    """Best-scoring unused along-route place inside the gap that fits the spare time."""
    def eligible(place: dict[str, Any]) -> bool:
        progress = _progress(place)
        return (
            place.get("recommendation_scope", "along_route") == "along_route"
            and place.get("id") not in used_ids
            and progress is not None and gap[0] <= progress <= gap[1]
            and candidate_is_plannable(place)
            and fits_spare(place, spare_minutes)
        )
    return max(filter(eligible, candidates), key=lambda place: float(place.get("enjoyment_score") or 0), default=None)


def parse_day_time(day: str, clock: str | None) -> datetime | None:
    try:
        return datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def _search_segment(gap: tuple[float, float]) -> tuple[float, float]:
    margin = (gap[1] - gap[0]) * GAP_EDGE_MARGIN
    return gap[0] + margin, gap[1] - margin


def _fill_context(result: dict[str, Any], request: Any, gap: tuple[float, float], spare_minutes: int) -> RouteAgentContext:
    stops = [item for item in result.get("itinerary", []) if item.get("kind") != "stay"]
    previous = next((item for item in reversed(stops) if (_progress(item) or 0) <= gap[0] and _progress(item) is not None), None)
    following = next((item for item in stops if (_progress(item) or 0) >= gap[1]), None)
    if previous:
        leave = parse_day_time(previous.get("date", request.start_date), previous.get("time", ""))
        arrival = leave + timedelta(minutes=int(previous.get("duration_min") or 0)) if leave else None
    else:
        arrival = parse_day_time(request.start_date, request.start_time)
    return RouteAgentContext(
        start=request.start,
        destination=request.destination,
        budget_per_person=request.budget_per_person,
        crowd_tolerance=request.crowd_tolerance,
        route_mode=request.route_mode,
        segment_start_progress_km=_search_segment(gap)[0],
        segment_end_progress_km=_search_segment(gap)[1],
        target_progress_km=(gap[0] + gap[1]) / 2,
        arrival=arrival,
        current_stop_cost_sgd=None,
        remaining_budget_per_person_sgd=None,
        selected_stop_title="",
        previous_stop_title=previous.get("title", "the start") if previous else "the start",
        next_stop_title=following.get("title", "check-in") if following else "check-in",
        query=fill_query(list(result.get("learned_preferences") or [])),
        mode="fill",
        spare_minutes=spare_minutes,
    )


async def _suggest_fill(result: dict[str, Any], request: Any, spare_minutes: int, provider: Any, agent_allowed: Callable[[], bool]) -> dict[str, Any] | None:
    route = result.get("route") or {}
    gap = longest_gap(result.get("itinerary", []), float(route.get("distance_km") or 0))
    agent = await run_route_agent(_fill_context(result, request, gap, spare_minutes), provider) if agent_allowed() else None
    if agent is not None and agent.candidates:
        return {"candidates": agent.candidates, "rationale": agent.rationale, "trace": agent.trace, "source": "agent"}
    used_ids = {str(item.get("place_id")) for item in result.get("itinerary", []) if item.get("place_id")}
    pick = deterministic_fill(result.get("candidate_places", []), _search_segment(gap), used_ids, spare_minutes)
    if pick is None:
        # The agent searched and found nothing that fits: say so, with its trace, rather than staying silent.
        return {"candidates": [], "rationale": agent.rationale, "trace": agent.trace, "source": "agent"} if agent is not None else None
    rationale = f"{pick.get('name', 'This stop')} sits on the longest open stretch and fits your {spare_minutes} spare minutes."
    return {"candidates": [pick], "rationale": rationale, "trace": [], "source": "deterministic"}


async def build_make_room(result: dict[str, Any], request: Any, deadline: Deadline | None, provider: Any, agent_allowed: Callable[[], bool]) -> dict[str, Any]:
    """Outcome of planning around the destination activity, plus an optional fill suggestion."""
    route = result.get("route") or {}
    arrival = parse_day_time(route.get("estimated_arrival_date", request.start_date), route.get("estimated_arrival_time", ""))
    room: dict[str, Any] = {
        "status": "no_hours",
        "destination_place_id": (request.destination_activity or {}).get("id"),
        "deadline": deadline.deadline.strftime("%H:%M") if deadline else None,
        "closes_at": deadline.closes_at.strftime("%H:%M") if deadline else None,
        "arrival": route.get("estimated_arrival_time"),
        "spare_minutes": None,
        "suggestion": None,
    }
    if deadline is None or arrival is None:
        return room
    if arrival > deadline.deadline:
        return {**room, "status": "wont_fit"}
    spare_minutes = int((deadline.deadline - arrival).total_seconds() // 60)
    suggestion = await _suggest_fill(result, request, spare_minutes, provider, agent_allowed) if spare_minutes >= FILL_TRIGGER_MINUTES else None
    return {**room, "status": "fits", "spare_minutes": spare_minutes, "suggestion": suggestion}
