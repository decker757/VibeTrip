"""Opening-hours helpers shared by the planner and its repair/verification steps."""

from datetime import datetime, timedelta
from typing import Any


def _opening_period_minutes(period_point: dict[str, Any] | None) -> int | None:
    if not period_point or period_point.get("day") is None:
        return None
    day = int(period_point.get("day", 0)) % 7
    hour = int(period_point.get("hour", 0))
    minute = int(period_point.get("minute", 0))
    return day * 24 * 60 + hour * 60 + minute


WEEK_MINUTES = 7 * 24 * 60
# Planned visit length by category: a starting value the traveller can change per stop.
VISIT_MINUTES_FUEL = 15
VISIT_MINUTES_FOOD = 60
VISIT_MINUTES_DEFAULT = 90
FUEL_TERMS = ("gas", "fuel", "petrol")
FOOD_TERMS = ("restaurant", "cafe", "food", "bakery")


def visit_minutes(place: dict[str, Any]) -> int:
    category = str(place.get("category") or "").lower()
    if any(term in category for term in FUEL_TERMS):
        return VISIT_MINUTES_FUEL
    return VISIT_MINUTES_FOOD if any(term in category for term in FOOD_TERMS) else VISIT_MINUTES_DEFAULT


def _minutes_left_open(periods: list[dict[str, Any]], arrival: datetime) -> list[int | None]:
    """For each period open at ``arrival``: minutes until it closes (None when it never closes)."""
    target = ((arrival.weekday() + 1) % 7) * 24 * 60 + arrival.hour * 60 + arrival.minute
    left: list[int | None] = []
    for period in periods:
        opened = _opening_period_minutes(period.get("open"))
        if opened is None:
            continue
        closed = _opening_period_minutes(period.get("close"))
        if closed is None:
            left.append(None)
            continue
        if closed <= opened:
            closed += WEEK_MINUTES
        for offset in (-WEEK_MINUTES, 0, WEEK_MINUTES):
            if opened + offset <= target < closed + offset:
                left.append(closed + offset - target)
    return left


def _periods(place: dict[str, Any]) -> list[dict[str, Any]]:
    return (place.get("opening_hours") or {}).get("periods") or []


def opening_status_at(place: dict[str, Any], arrival: datetime) -> bool | None:
    """Return scheduled opening status, or None when Google has no periods."""
    periods = _periods(place)
    return bool(_minutes_left_open(periods, arrival)) if periods else None


def open_for(place: dict[str, Any], arrival: datetime, minutes: int) -> bool | None:
    """True when the place stays open from ``arrival`` for the whole visit; None without hours."""
    periods = _periods(place)
    if not periods:
        return None
    return any(left is None or left >= minutes for left in _minutes_left_open(periods, arrival))


def closing_time(place: dict[str, Any], arrival: datetime) -> datetime | None:
    """When the window you arrive in closes; None if closed at arrival, open round the clock, or no hours."""
    left = _minutes_left_open(_periods(place), arrival)
    if not left or None in left:
        return None
    return arrival + timedelta(minutes=max(left))


def candidate_is_plannable(place: dict[str, Any]) -> bool:
    """Use regular hours when available; open_now is only a fallback."""
    return bool(place.get("opening_hours", {}).get("periods")) or place.get("open_now", True)
