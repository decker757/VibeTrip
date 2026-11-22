"""Locked stops: the traveller's own choices survive a regenerate; the planner plans around them."""

from backend.graph import day_builder
from backend.repair import available_actions
from backend.tests.planner_helpers import run_deterministic_planner
from backend.tests.test_providers import _encode_polyline

FRIDAY = 5  # 2026-11-20, the demo trip date


def _locked(id, progress, kind, duration, category="Restaurant", **extra):
    return {"id": id, "name": id, "category": category, "route_progress_km": progress, "kind": kind, "duration_min": duration, **extra}


def _by_id(result):
    return {item.get("place_id"): item for item in result["itinerary"]}


def test_a_locked_restaurant_covers_lunch_with_its_own_duration(demo_state):
    state = {**demo_state("balanced"), "locked_stops": [_locked("my-diner", 150, "meal", 40)]}
    stops = _by_id(run_deterministic_planner(state))
    assert stops["my-diner"]["duration_min"] == 40 and stops["my-diner"]["locked"] is True
    assert "demo-lunch" not in stops


def test_a_locked_fuel_stop_is_the_first_fuel_and_the_second_is_spaced_from_it():
    fuel = lambda id, km: {"id": id, "name": id, "category": "Gas station", "route_progress_km": km, "detour_minutes": 2, "open_now": True}
    state = {"route_mode": "balanced", "start_date": "2026-11-20", "start_time": "06:00", "selected_places": [],
             "route": {"distance_km": 600, "drive_minutes": 480},
             "candidate_places": [fuel("f200", 200), fuel("f420", 420)],
             "locked_stops": [_locked("my-fuel", 100, "fuel", 15, category="Gas station")]}
    fuels = [item["place_id"] for item in day_builder(state)["itinerary"] if item["kind"] == "fuel"]
    assert fuels == ["my-fuel", "f420"]  # f200 is only 100 km after the locked station


def test_a_locked_stop_closed_for_the_visit_is_kept_and_flagged(demo_state):
    hours = {"periods": [{"open": {"day": FRIDAY, "hour": 6, "minute": 0}, "close": {"day": FRIDAY, "hour": 7, "minute": 0}}]}
    state = {**demo_state("balanced"), "locked_stops": [_locked("my-museum", 180, "attraction", 60, category="Museum", opening_hours=hours)]}
    museum = _by_id(run_deterministic_planner(state))["my-museum"]
    assert museum["closed_during_visit"] is True


def test_locked_destination_activities_come_last_in_the_travellers_order(demo_state):
    state = {**demo_state("balanced"), "locked_stops": [
        _locked("museum-first", 340, "activity", 90, category="Museum"),
        _locked("market-second", 300, "activity", 60, category="Food court"),
    ]}
    order = [item.get("place_id") for item in run_deterministic_planner(state)["itinerary"]]
    assert order[-3:] == ["museum-first", "market-second", None]  # None is check-in


def test_repair_never_offers_to_skip_a_locked_stop():
    itinerary = [{"kind": "coffee", "locked": True}, {"kind": "fuel"}, {"kind": "meal"}, {"kind": "attraction"}]
    assert available_actions({"itinerary": itinerary}) == ["skip_attraction", "accept_warning"]


def test_a_locked_stop_is_re_placed_on_a_new_route(demo_state):
    # Route runs north along longitude 103.80; the locked stop sits 0.5 degrees (~56 km) in.
    polyline = _encode_polyline([(1.30 + i * 0.05, 103.80) for i in range(21)])
    state = {**demo_state("balanced"), "locked_stops": [_locked("my-diner", 999, "meal", 40, location={"latitude": 1.80, "longitude": 103.80})]}
    state["route"] = {**state["route"], "polyline": polyline}
    progress = _by_id(run_deterministic_planner(state))["my-diner"]["route_progress_km"]
    assert 50 <= progress <= 62


def test_plan_endpoint_keeps_locked_stops_and_returns_them_as_places(auth_client):
    plan = auth_client.post("/trips/plan", json={
        "start": "Singapore", "destination": "KL", "start_date": "2026-11-20",
        "locked_stops": [_locked("my-diner", 150, "meal", 40, address="1 Food St")],
    }).json()
    assert "my-diner" in [item.get("place_id") for item in plan["itinerary"]]
    assert any(place["id"] == "my-diner" for place in plan["candidate_places"])
