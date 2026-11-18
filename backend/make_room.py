"""Make room for the destination: plan the drive around what the traveller wants to do there.

The deadline comes from the chosen place's opening hours, not from a clock time
the traveller has to guess. The planner then trims optional stops when the drive
runs late (repair.py in make-room mode), or offers one stop to fill spare time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

VISIT_MINUTES_FOOD = 60
VISIT_MINUTES_DEFAULT = 90
FOOD_TERMS = ("restaurant", "cafe", "food", "bakery")
LAST_MINUTE_OF_DAY = time(23, 59)


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
