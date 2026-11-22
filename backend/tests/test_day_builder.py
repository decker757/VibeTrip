"""Characterisation tests: pin today's day_builder behaviour before refactoring."""

import json
from pathlib import Path

import pytest

from backend.tests.planner_helpers import build_demo_state, run_deterministic_planner

GOLDEN = Path(__file__).parent / "fixtures" / "day_builder_golden.json"
CASES = [(mode, end) for mode in ("fastest", "balanced", "scenic") for end in ("18:00", "12:00")]


def _golden_key(mode: str, end_time: str) -> str:
    return f"{mode}@{end_time}"


def _kinds(result: dict) -> list[str]:
    return [item["kind"] for item in result["itinerary"]]


@pytest.mark.parametrize("mode,end_time", CASES)
def test_matches_golden(mode, end_time):
    golden = json.loads(GOLDEN.read_text())[_golden_key(mode, end_time)]
    result = run_deterministic_planner(build_demo_state(mode, end_time))
    assert result["itinerary"] == golden["itinerary"]
    # Later tasks may add route keys; every key captured today must still match.
    assert {key: result["route"].get(key) for key in golden["route"]} == golden["route"]


def test_balanced_order_follows_route_progress(demo_state):
    assert _kinds(run_deterministic_planner(demo_state("balanced"))) == ["coffee", "fuel", "attraction", "meal", "stay"]


def test_fastest_has_fuel_and_no_coffee(demo_state):
    kinds = _kinds(run_deterministic_planner(demo_state("fastest")))
    assert "fuel" in kinds and "coffee" not in kinds


def test_closed_at_arrival_is_skipped(demo_state):
    state = demo_state("balanced")
    for place in state["candidate_places"]:
        if place["id"] == "demo-coffee":
            # 2026-11-20 is a Friday (Google day 5); open 06:00-08:00, coffee would arrive ~09:10.
            place["opening_hours"] = {"periods": [{"open": {"day": 5, "hour": 6, "minute": 0}, "close": {"day": 5, "hour": 8, "minute": 0}}]}
    assert "coffee" not in _kinds(run_deterministic_planner(state))


def test_late_arrival_warning(demo_state):
    route = run_deterministic_planner(demo_state("balanced", "12:00"))["route"]
    assert "later than your target end time of 12:00" in route["schedule_warning"]


def test_structured_late_warning(demo_state):
    route = run_deterministic_planner(demo_state("balanced", "12:00"))["route"]
    assert [w["code"] for w in route["warnings"]] == ["late_arrival"]
    assert route["arrival_offset_minutes"] == 415  # 08:10 -> 15:05


def test_no_warnings_list_empty(demo_state):
    assert run_deterministic_planner(demo_state("balanced"))["route"]["warnings"] == []


def test_multi_day_metadata(demo_state):
    state = demo_state("balanced")
    state["route"] = {**state["route"], "drive_minutes": 1500, "distance_km": 2000}
    stay = run_deterministic_planner(state)["itinerary"][-1]
    assert stay["kind"] == "stay" and stay["day_number"] >= 2 and stay["date"] > "2026-11-20"


if __name__ == "__main__":
    # Regenerate only when behaviour is intentionally changed: python -m backend.tests.test_day_builder
    snapshot = {}
    for mode, end_time in CASES:
        result = run_deterministic_planner(build_demo_state(mode, end_time))
        snapshot[_golden_key(mode, end_time)] = {"itinerary": result["itinerary"], "route": result["route"]}
    GOLDEN.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(f"wrote {GOLDEN}")


# --- Stop timing: fuel and lunch by where on the route you'd need them ---
from backend.graph import _order_near_target, _pick_stop_options


def _cand(id, progress, category="Gas station", detour=2):
    return {"id": id, "name": id, "category": category, "route_progress_km": progress, "detour_minutes": detour, "open_now": True}


def _timing_state(candidates, start_time="08:10", distance_km=600, drive_minutes=480):
    return {"route_mode": "balanced", "start_date": "2026-11-20", "start_time": start_time,
            "route": {"distance_km": distance_km, "drive_minutes": drive_minutes},
            "candidate_places": candidates, "selected_places": []}


def test_order_near_target_keeps_rank_inside_window():
    options = [_cand("a", 100), _cand("b", 200), _cand("c", 150), _cand("d", None), _cand("e", 165)]
    assert [o["id"] for o in _order_near_target(options, 160, 30)] == ["c", "e", "b", "a", "d"]


def test_second_fuel_is_spaced_from_first():
    picks = _pick_stop_options(_timing_state([_cand("f200", 200), _cand("f201", 201, detour=1), _cand("f410", 410, detour=5)]))
    assert picks.fuel_stop["id"] in {"f200", "f201"}
    assert picks.second_fuel_after(picks.fuel_stop)["id"] == "f410"


def test_no_second_fuel_when_none_is_far_enough():
    picks = _pick_stop_options(_timing_state([_cand("f200", 200), _cand("f201", 201)]))
    assert picks.second_fuel_after(picks.fuel_stop) is None


def test_meal_targets_lunch_time():
    # 600 km in 480 min = 1.25 km/min; from 06:00, 12:30 is 390 min in, 487 km, clamped to 80% = 480 km.
    meals = [_cand("r100", 100, "Restaurant"), _cand("r290", 290, "Restaurant"), _cand("r500", 500, "Restaurant")]
    assert _pick_stop_options(_timing_state(meals, start_time="06:00")).meal_options[0]["id"] == "r500"


def test_meal_targets_midpoint_when_drive_misses_lunch():
    meals = [_cand("r100", 100, "Restaurant"), _cand("r290", 290, "Restaurant"), _cand("r500", 500, "Restaurant")]
    assert _pick_stop_options(_timing_state(meals, start_time="13:00")).meal_options[0]["id"] == "r290"


def test_ranked_meal_kept_when_inside_window():
    meals = [_cand("r100", 100, "Restaurant"), _cand("r290", 290, "Restaurant"), _cand("r330", 330, "Restaurant")]
    state = {**_timing_state(meals, start_time="13:00"), "selected_places": [meals[2]]}
    assert _pick_stop_options(state).meal_options[0]["id"] == "r330"  # the reviewer's pick, within ±90 km of 300


@pytest.mark.parametrize("mode", ["fastest", "balanced"])
def test_closed_first_fuel_falls_back_to_next_station_and_respaces_second(mode):
    # Long drive: the best-placed station is closed when you'd arrive; the open one 10 km on should be used,
    # and the second fuel stop spaced from that one, not from the closed one.
    from backend.graph import day_builder
    closed = {**_cand("f200", 200), "opening_hours": {"periods": [{"open": {"day": 5, "hour": 6, "minute": 0}, "close": {"day": 5, "hour": 7, "minute": 0}}]}}
    state = {**_timing_state([closed, _cand("f210", 210, detour=3), _cand("f420", 420), _cand("r300", 300, "Restaurant")]), "route_mode": mode}
    fuel_ids = [item["place_id"] for item in day_builder(state)["itinerary"] if item["kind"] == "fuel"]
    assert fuel_ids == ["f210", "f420"]


# --- Leg timing: each drive between stops reflects that stretch of road ---
from backend.graph import day_builder as _day_builder


def _phoenix_to_la(route_extra=None):
    """Phoenix -> LA (600 km, 360 min from 09:30): Quartzsite, Coachella, two stops in Indio, then Redlands."""
    places = [
        _cand("quartzsite", 205), _cand("coachella", 390),
        {**_cand("casino", 395, "Tourist attraction"), "recommendation_kind": "scenic", "recommendation_scope": "along_route"},
        _cand("indio-lunch", 398, "Restaurant"), _cand("redlands-cafe", 495, "Cafe"),
    ]
    state = _timing_state(places, start_time="09:30", distance_km=600, drive_minutes=360)
    state["route"].update(route_extra or {})
    return _day_builder(state)


def _drive_gaps(itinerary):
    """Minutes between leaving each item and reaching the next, as the timeline shows them."""
    return [nxt["schedule_offset_minutes"] - cur["schedule_offset_minutes"] - cur["duration_min"] for cur, nxt in zip(itinerary, itinerary[1:])]


def test_short_hops_do_not_borrow_time_from_the_next_long_leg():
    itinerary = _phoenix_to_la()["itinerary"]
    assert [item["place_id"] for item in itinerary[:-1]] == ["quartzsite", "coachella", "casino", "indio-lunch", "redlands-cafe"]
    # Indio -> Redlands is 97 km: 58 min of driving plus its 20% buffer share, not the old 25 min floor.
    assert 65 <= _drive_gaps(itinerary)[3] <= 75


def test_buffer_is_spread_across_legs_not_added_to_the_last():
    itinerary = _phoenix_to_la()["itinerary"]
    # Redlands -> LA is 105 km: about 63 min plus its buffer share, not 51 min plus the whole 72 min buffer.
    assert 70 <= _drive_gaps(itinerary)[-1] <= 82


ROUTED_IDS = ["quartzsite", "coachella", "casino", "indio-lunch", "redlands-cafe"]
REAL_LEGS = [120, 110, 10, 5, 70, 80]  # Google per-leg minutes; sums to 395


def test_real_leg_times_are_used_when_route_was_plotted_through_the_stops():
    result = _phoenix_to_la({"routed_waypoint_ids": ROUTED_IDS, "leg_minutes": REAL_LEGS, "drive_minutes": 395})
    gaps = _drive_gaps(result["itinerary"])
    first_leg = result["itinerary"][0]["schedule_offset_minutes"]
    # Each leg carries the same 20% buffer share (79 of 395 min).
    assert [first_leg, *gaps] == [round(sum(REAL_LEGS[: i + 1]) * 1.2) - round(sum(REAL_LEGS[:i]) * 1.2) for i in range(len(REAL_LEGS))]


def test_real_leg_times_ignored_when_stops_differ_from_routed_waypoints():
    result = _phoenix_to_la({"routed_waypoint_ids": ["somewhere-else"], "leg_minutes": [1, 1, 1, 1, 1, 390], "drive_minutes": 395})
    # Falls back to the distance estimate: Quartzsite is 205 of 600 km.
    assert result["itinerary"][0]["schedule_offset_minutes"] > 100


def test_stop_after_a_closed_one_keeps_its_real_arrival_time():
    closed_casino = {"periods": [{"open": {"day": 5, "hour": 6, "minute": 0}, "close": {"day": 5, "hour": 7, "minute": 0}}]}
    places = [
        _cand("quartzsite", 205), _cand("coachella", 390),
        {**_cand("casino", 395, "Tourist attraction"), "recommendation_kind": "scenic", "recommendation_scope": "along_route", "opening_hours": closed_casino},
        _cand("indio-lunch", 398, "Restaurant"), _cand("redlands-cafe", 495, "Cafe"),
    ]
    state = _timing_state(places, start_time="09:30", distance_km=600, drive_minutes=395)
    state["route"].update({"routed_waypoint_ids": ROUTED_IDS, "leg_minutes": REAL_LEGS})
    itinerary = _day_builder(state)["itinerary"]
    lunch = next(item for item in itinerary if item["place_id"] == "indio-lunch")
    assert "casino" not in [item.get("place_id") for item in itinerary]
    # Real drive to lunch is 245 min (+20% buffer), plus the two 15-min fuel stops.
    assert lunch["schedule_offset_minutes"] == round(245 * 1.2) + 30
