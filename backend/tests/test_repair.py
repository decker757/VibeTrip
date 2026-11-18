import asyncio
from unittest.mock import ANY

from backend.graph import day_builder, planner_graph
from backend.repair import RepairDecision, available_actions, finalize_best, repair_until_settled, should_repair


def run_graph(state: dict) -> dict:
    return asyncio.run(planner_graph.ainvoke(state))


class FakeStructuredModel:
    """Stands in for a chat model: with_structured_output(...).invoke(...) returns a preset decision."""

    def __init__(self, decision):
        self.decision = decision
        self.calls = 0

    def with_structured_output(self, schema):
        model = self

        class Runner:
            def invoke(self, messages):
                model.calls += 1
                if isinstance(model.decision, Exception):
                    raise model.decision
                return model.decision

        return Runner()


def test_fixable_late_trip_skips_stops_and_clears_warning(demo_state):
    out = run_graph(demo_state("balanced", "14:30"))  # arrives 15:05 before repair
    assert out["route"]["warnings"] == []
    assert out["route"]["schedule_warning"] is None
    assert [e["action"] for e in out["repair_log"]] == ["skip_coffee", "skip_attraction"]
    assert all(e["source"] == "rule" for e in out["repair_log"])
    kinds = [i["kind"] for i in out["itinerary"]]
    assert "meal" in kinds and "fuel" in kinds
    assert "coffee" not in kinds and "attraction" not in kinds
    assert out["repair_attempts"] == 2


def test_unfixable_trip_is_not_stripped(demo_state):
    out = run_graph(demo_state("balanced", "12:00"))
    assert [i["kind"] for i in out["itinerary"]] == ["coffee", "fuel", "attraction", "meal", "stay"]
    assert out["repair_log"] == [{"attempt": 1, "warning": ANY, "action": "accept_warning", "reason": "Unfixable without changing route mode", "source": "rule"}]
    assert out["route"]["schedule_warning"].endswith("Start earlier, allow a later end time, or try Fastest.")
    assert out["route"]["schedule_warning"].count("or try Fastest") == 1


def test_no_optional_stops_means_no_repair(demo_state):
    out = run_graph(demo_state("fastest", "12:00"))
    assert out["repair_log"] == []
    assert out["route"]["warnings"][0]["code"] == "late_arrival"
    assert "Try Fastest" not in out["route"]["schedule_warning"]


def test_never_changes_route_mode(demo_state):
    for end_time in ("14:30", "12:00"):
        assert run_graph(demo_state("scenic", end_time))["route"]["route_mode"] == "scenic"


def test_on_time_trip_is_untouched(demo_state):
    out = run_graph(demo_state("balanced", "18:00"))
    assert out["repair_log"] == [] and out["route"]["warnings"] == []
    assert [i["kind"] for i in out["itinerary"]] == ["coffee", "fuel", "attraction", "meal", "stay"]


def test_available_actions_lists_optional_kinds_present(demo_state):
    built = day_builder(demo_state("balanced", "14:30"))
    assert available_actions(built) == ["skip_coffee", "skip_attraction", "accept_warning"]
    fastest = day_builder(demo_state("fastest", "12:00"))
    assert available_actions(fastest) == ["accept_warning"]


def test_llm_choice_is_used(demo_state, monkeypatch):
    model = FakeStructuredModel(RepairDecision(action="skip_attraction", reason="r"))
    monkeypatch.setattr("backend.repair.llm_enabled", lambda: True)
    monkeypatch.setattr("backend.repair.get_chat_model", lambda: model)
    out = run_graph(demo_state("balanced", "14:30"))
    assert out["repair_log"][0] == {"attempt": 1, "warning": ANY, "action": "skip_attraction", "reason": "r", "source": "llm"}
    assert model.calls >= 1


def test_invalid_llm_action_falls_back_to_rule(demo_state, monkeypatch):
    # No second fuel stop exists, so skip_extra_fuel is not on offer.
    monkeypatch.setattr("backend.repair.llm_enabled", lambda: True)
    monkeypatch.setattr("backend.repair.get_chat_model", lambda: FakeStructuredModel(RepairDecision(action="skip_extra_fuel", reason="r")))
    out = run_graph(demo_state("balanced", "14:30"))
    first = out["repair_log"][0]
    assert first["action"] == "skip_coffee" and first["source"] == "rule"


def test_none_llm_result_falls_back_to_rule(demo_state, monkeypatch):
    monkeypatch.setattr("backend.repair.llm_enabled", lambda: True)
    monkeypatch.setattr("backend.repair.get_chat_model", lambda: FakeStructuredModel(None))
    out = run_graph(demo_state("balanced", "14:30"))
    assert out["repair_log"][0]["action"] == "skip_coffee" and out["repair_log"][0]["source"] == "rule"


def test_failed_llm_call_falls_back_to_rule(demo_state, monkeypatch):
    monkeypatch.setattr("backend.repair.llm_enabled", lambda: True)
    monkeypatch.setattr("backend.repair.get_chat_model", lambda: FakeStructuredModel(RuntimeError("down")))
    out = run_graph(demo_state("balanced", "14:30"))
    assert [(e["action"], e["source"]) for e in out["repair_log"]] == [("skip_coffee", "rule"), ("skip_attraction", "rule")]


def test_llm_accept_warning_keeps_stops(demo_state, monkeypatch):
    monkeypatch.setattr("backend.repair.llm_enabled", lambda: True)
    monkeypatch.setattr("backend.repair.get_chat_model", lambda: FakeStructuredModel(RepairDecision(action="accept_warning", reason="keep it")))
    out = run_graph(demo_state("balanced", "14:30"))
    assert [(e["action"], e["source"]) for e in out["repair_log"]] == [("accept_warning", "llm")]
    assert [i["kind"] for i in out["itinerary"]] == ["coffee", "fuel", "attraction", "meal", "stay"]
    assert out["route"]["warnings"][0]["code"] == "late_arrival"


def test_finalize_keeps_best_snapshot():
    good = {"itinerary": [{"kind": "meal"}], "route": {"warnings": [], "arrival_offset_minutes": 300}, "skipped_stop_kinds": []}
    state = {
        "itinerary": [{"kind": "stay"}],
        "route": {"warnings": [{"code": "late_arrival", "message": "late"}], "arrival_offset_minutes": 280},
        "skipped_stop_kinds": ["coffee"],
        "repair_snapshots": [good],
    }
    out = finalize_best(state)
    assert out["itinerary"] == good["itinerary"] and out["route"] == good["route"]
    assert out["skipped_stop_kinds"] == [] and out["repair_snapshots"] == [] and out["repair_log"] == []


def test_repair_attempts_are_shared_with_post_reroute(demo_state):
    out = run_graph(demo_state("balanced", "14:30"))
    assert out["repair_attempts"] == 2
    late_again = day_builder({**out, "skipped_stop_kinds": [], "end_time": "13:00"})
    after = repair_until_settled(late_again, day_builder)
    assert after["repair_attempts"] == 2 and len(after["repair_log"]) == 2


def test_plan_returns_repair_log(auth_client):
    r = auth_client.post("/trips/plan", json={"start": "Singapore", "destination": "KL", "start_date": "2026-11-20", "end_time": "12:00"})
    assert r.status_code == 200
    assert r.json()["repair_log"][0]["action"] == "accept_warning"
    assert "Start earlier, allow a later end time, or try Fastest." in r.json()["warning"]


def test_make_room_mode_never_offers_accept_warning(demo_state, monkeypatch):
    model = FakeStructuredModel(RepairDecision(action="accept_warning", reason="keep all"))
    monkeypatch.setattr("backend.repair.llm_enabled", lambda: True)
    monkeypatch.setattr("backend.repair.get_chat_model", lambda: model)
    out = run_graph({**demo_state("balanced", "14:30"), "make_room_mode": True})
    assert model.calls > 0
    assert out["route"]["warnings"] == []
    assert all(e["action"] != "accept_warning" for e in out["repair_log"])
    assert all(e["source"] == "rule" for e in out["repair_log"])


def test_make_room_mode_allows_a_third_attempt():
    late = {"route": {"warnings": [{"code": "late_arrival", "message": "late"}]}, "itinerary": [{"kind": "coffee"}], "repair_attempts": 2}
    assert should_repair(late) == "finalize"
    assert should_repair({**late, "make_room_mode": True}) == "repair"
