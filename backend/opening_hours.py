"""Opening-hours helpers shared by the planner and its repair/verification steps."""

from datetime import datetime
from typing import Any


def _opening_period_minutes(period_point: dict[str, Any] | None) -> int | None:
    if not period_point or period_point.get("day") is None:
        return None
    day = int(period_point.get("day", 0)) % 7
    hour = int(period_point.get("hour", 0))
    minute = int(period_point.get("minute", 0))
    return day * 24 * 60 + hour * 60 + minute


def opening_status_at(place: dict[str, Any], arrival: datetime) -> bool | None:
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


def candidate_is_plannable(place: dict[str, Any]) -> bool:
    """Use regular hours when available; open_now is only a fallback."""
    return bool(place.get("opening_hours", {}).get("periods")) or place.get("open_now", True)
