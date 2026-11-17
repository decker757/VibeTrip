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
