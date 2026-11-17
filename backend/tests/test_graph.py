from backend.graph import planner_graph
from backend.providers import DemoMapsProvider


def base_request_state() -> dict:
    return {
        "start": "Singapore",
        "destination": "Kuala Lumpur",
        "travellers": 4,
        "budget_per_person": 400,
        "start_date": "2026-11-20",
        "end_date": "2026-11-20",
        "start_time": "08:10",
        "end_time": "18:00",
        "preferences": [],
        "adventure_level": 70,
        "crowd_tolerance": "medium",
        "route_mode": "balanced",
    }


async def test_route_scout_uses_injected_provider():
    out = await planner_graph.ainvoke(base_request_state(), config={"configurable": {"maps_provider": DemoMapsProvider()}})
    assert out["provider_name"] == "demo" and out["candidate_places"]
    assert out["itinerary"][-1]["kind"] == "stay"


async def test_route_scout_falls_back_on_provider_error():
    class Boom:
        async def plan_trip(self, *args, **kwargs):
            raise RuntimeError("x")

    out = await planner_graph.ainvoke(base_request_state(), config={"configurable": {"maps_provider": Boom()}})
    assert out["provider_name"] == "demo"
    assert "Maps provider unavailable (RuntimeError)" in out["provider_warning"]


def test_plan_endpoint_still_works(auth_client):
    response = auth_client.post("/trips/plan", json={"start": "Singapore", "destination": "Kuala Lumpur", "start_date": "2026-11-20"})
    body = response.json()
    assert response.status_code == 200 and body["itinerary"][-1]["kind"] == "stay" and body["provider"] == "demo"
