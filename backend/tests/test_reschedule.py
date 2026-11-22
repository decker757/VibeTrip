"""Manual stop edits: re-time the traveller's own stop order with the planner's drive clock."""

from backend.graph import schedule_given_stops

# 2026-11-30 is a Monday (Google day 1).
MONDAY_10_TO_17 = {"periods": [{"open": {"day": 1, "hour": 10, "minute": 0}, "close": {"day": 1, "hour": 17, "minute": 0}}]}
ROUTE = {"drive_minutes": 400, "distance_km": 600, "routed_waypoint_ids": ["fuel", "museum", "market"], "leg_minutes": [200, 150, 20, 30]}


def _stops(museum_hours=None):
    return [
        {"id": "fuel", "duration_min": 15},
        {"id": "museum", "duration_min": 45, **({"opening_hours": museum_hours} if museum_hours else {})},
        {"id": "market", "duration_min": 45},
    ]


def _times(schedule):
    return {item["id"]: item["schedule_offset_minutes"] for item in schedule["stops"]}


def test_stops_keep_the_travellers_order_and_check_in_comes_after_the_last():
    schedule = schedule_given_stops(ROUTE, _stops(), "2026-11-30", "08:00")
    times = _times(schedule)
    assert [item["id"] for item in schedule["stops"]] == ["fuel", "museum", "market"]
    assert times["fuel"] < times["museum"] < times["market"]
    # Real legs plus a 20% buffer share each: market ends at 370*1.2 + 105, then the last 30-min leg.
    assert times["market"] == round(370 * 1.2) + 60
    assert schedule["arrival"]["schedule_offset_minutes"] == round(400 * 1.2) + 105


def test_a_stop_closed_on_arrival_is_kept_and_flagged():
    # Museum reached at 08:00 + 350*1.2 + 15 = 15:15 -> open; start at 12:00 and it's 19:15 -> closed.
    open_schedule = schedule_given_stops(ROUTE, _stops(MONDAY_10_TO_17), "2026-11-30", "08:00")
    late_schedule = schedule_given_stops(ROUTE, _stops(MONDAY_10_TO_17), "2026-11-30", "12:00")
    assert not any(item["closed_on_arrival"] for item in open_schedule["stops"])
    museum = next(item for item in late_schedule["stops"] if item["id"] == "museum")
    assert museum["closed_on_arrival"] and museum["time"] == "19:15"
    assert [item["id"] for item in late_schedule["stops"]] == ["fuel", "museum", "market"]


def test_reroute_returns_a_schedule_for_the_edited_stops(auth_client):
    response = auth_client.post("/trips/reroute", json={
        "start": "Phoenix, AZ", "destination": "Los Angeles, CA", "start_date": "2026-11-30", "start_time": "08:00",
        "route": {"drive_minutes": 360, "distance_km": 600},
        "stops": [{"id": "a", "duration_min": 15, "route_progress_km": 200}, {"id": "b", "duration_min": 45, "route_progress_km": 590}],
    })
    schedule = response.json()["schedule"]
    last = schedule["stops"][-1]
    assert [item["id"] for item in schedule["stops"]] == ["a", "b"]
    assert schedule["arrival"]["schedule_offset_minutes"] > last["schedule_offset_minutes"] + 45
