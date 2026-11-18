from datetime import date, datetime

from backend.make_room import deterministic_fill, destination_deadline, fill_query, longest_gap
from backend.route_agent import RouteAgentResult

ON = date(2026, 11, 20)  # a Friday; Google weekday 5


def period(open_h, close_h, day=5, close_day=None):
    return {
        "open": {"day": day, "hour": open_h, "minute": 0},
        "close": {"day": close_day if close_day is not None else day, "hour": close_h, "minute": 0},
    }


def place(*periods, category="Art Museum"):
    return {"id": "p", "name": "P", "category": category, "opening_hours": {"periods": list(periods)}}


def test_single_window_deadline_is_close_minus_visit():
    d = destination_deadline(place(period(10, 17)), ON, datetime(2026, 11, 20, 13, 40))
    assert d.deadline == datetime(2026, 11, 20, 15, 30)
    assert d.closes_at == datetime(2026, 11, 20, 17, 0)
    assert d.visit_minutes == 90


def test_food_visit_is_60_minutes():
    assert destination_deadline(place(period(10, 22), category="Food Court"), ON, None).deadline == datetime(2026, 11, 20, 21, 0)


def test_split_hours_picks_first_window_still_reachable():
    d = destination_deadline(place(period(11, 14), period(17, 22)), ON, datetime(2026, 11, 20, 15, 0))
    assert d.deadline == datetime(2026, 11, 20, 20, 30)


def test_split_hours_picks_earliest_window_when_both_reachable():
    d = destination_deadline(place(period(17, 22), period(11, 14)), ON, datetime(2026, 11, 20, 9, 0))
    assert d.deadline == datetime(2026, 11, 20, 12, 30)


def test_no_reachable_window_uses_last_window():
    d = destination_deadline(place(period(9, 13)), ON, datetime(2026, 11, 20, 15, 5))
    assert d.deadline == datetime(2026, 11, 20, 11, 30)


def test_after_midnight_close_is_capped():
    d = destination_deadline(place(period(18, 2, close_day=6)), ON, None)
    assert d.closes_at == datetime(2026, 11, 20, 23, 59)


def test_open_24_hours_has_no_deadline():
    assert destination_deadline(place({"open": {"day": 0, "hour": 0, "minute": 0}}), ON, None) is None


def test_no_periods_that_day_has_no_deadline():
    assert destination_deadline(place(period(10, 17, day=1)), ON, None) is None
    assert destination_deadline({"id": "p", "opening_hours": {}}, ON, None) is None


BODY = {"start": "Singapore", "destination": "KL", "start_date": "2026-11-20", "current_arrival_time": "15:05"}
# Demo plan: arrives 15:05 with every stop, 13:55 after skipping coffee and the attraction.


def test_plain_plan_has_no_make_room(auth_client):
    assert "make_room" not in auth_client.post("/trips/plan", json=BODY).json()


def test_fits_with_trim_against_real_deadline(auth_client):
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": place(period(10, 16))}).json()  # deadline 14:30
    room = r["make_room"]
    assert room["status"] == "fits" and room["deadline"] == "14:30" and room["closes_at"] == "16:00"
    assert room["arrival"] == "13:55" and room["spare_minutes"] == 35 and room["suggestion"] is None
    assert [e["action"] for e in r["repair_log"]] == ["skip_coffee", "skip_attraction"]


def test_closed_before_arrival_wont_fit(auth_client):
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": place(period(9, 13))}).json()  # deadline 11:30
    assert r["make_room"]["status"] == "wont_fit" and r["make_room"]["suggestion"] is None


def test_no_hours_plans_with_default_end_time(auth_client):
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": {"id": "x", "name": "X", "opening_hours": {}}}).json()
    assert r["make_room"]["status"] == "no_hours" and r["make_room"]["deadline"] is None
    assert r["repair_log"] == []


def test_spare_time_runs_agent_fill(auth_client, monkeypatch):
    seen = {}

    async def fake_agent(context, provider, model=None):
        seen["context"] = context
        return RouteAgentResult(candidates=[{"id": "demo-coffee", "name": "C", "detour_minutes": 3}], rationale="fits", trace=[{"step": 1}])

    monkeypatch.setattr("backend.make_room.run_route_agent", fake_agent)
    monkeypatch.setattr("backend.main._route_agent_allowed", lambda: True)
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": place(period(10, 21))}).json()  # deadline 19:30
    room = r["make_room"]
    assert room["status"] == "fits" and room["spare_minutes"] == 265
    assert room["suggestion"] == {"candidates": [{"id": "demo-coffee", "name": "C", "detour_minutes": 3}], "rationale": "fits", "trace": [{"step": 1}], "source": "agent"}
    context = seen["context"]
    assert context.mode == "fill" and context.spare_minutes == 265
    assert (context.segment_start_progress_km, context.segment_end_progress_km) == (205, 348)


def test_spare_time_without_agent_falls_back_to_deterministic(auth_client):
    # LLM is off in tests; the longest gap (205-348 km) has no unused along-route place, so no suggestion.
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": place(period(10, 21))}).json()
    assert r["make_room"]["status"] == "fits" and r["make_room"]["suggestion"] is None


def test_little_spare_time_does_not_run_agent(auth_client, monkeypatch):
    async def fail(*args, **kwargs):
        raise AssertionError("agent must not run")

    monkeypatch.setattr("backend.make_room.run_route_agent", fail)
    monkeypatch.setattr("backend.main._route_agent_allowed", lambda: True)
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": place(period(10, 16))}).json()
    assert r["make_room"]["spare_minutes"] < 45 and r["make_room"]["suggestion"] is None


def test_longest_gap_and_fill_query():
    items = [{"route_progress_km": 65}, {"route_progress_km": 125}, {"route_progress_km": 300}, {"route_progress_km": None}]
    assert longest_gap(items, 340) == (125, 300)
    assert fill_query(["local_food", "scenic_views"]) == "scenic viewpoint or nature stop"
    assert fill_query(["local_food"]) == "local food spot"
    assert fill_query([]) == "worthwhile stop"


def test_deterministic_fill_picks_best_unused_place_that_fits():
    candidates = [
        {"id": "a", "route_progress_km": 150, "detour_minutes": 5, "enjoyment_score": 70},
        {"id": "b", "route_progress_km": 160, "detour_minutes": 5, "enjoyment_score": 90},
        {"id": "used", "route_progress_km": 170, "detour_minutes": 5, "enjoyment_score": 99},
        {"id": "far", "route_progress_km": 170, "detour_minutes": 40, "enjoyment_score": 95},
        {"id": "outside", "route_progress_km": 20, "detour_minutes": 5, "enjoyment_score": 98},
        {"id": "dest", "route_progress_km": 165, "detour_minutes": 5, "enjoyment_score": 97, "recommendation_scope": "destination"},
    ]
    assert deterministic_fill(candidates, (125, 300), {"used"}, 60)["id"] == "b"
    assert deterministic_fill(candidates, (125, 300), {"used", "a", "b"}, 60) is None
