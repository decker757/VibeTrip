from unittest.mock import AsyncMock

from backend.route_agent import RouteAgentResult

BODY = {
    "start": "Singapore",
    "destination": "Kuala Lumpur",
    "query": "a quiet cafe",
    "segment_start_progress_km": 0,
    "segment_end_progress_km": 100,
}


def _agent_returning(candidates):
    async def fake(context, provider, model=None):
        fake.context = context
        return RouteAgentResult(
            candidates=candidates,
            rationale="Quiet and open on arrival.",
            trace=[{"step": 1, "tool": "search_places", "summary": "Found 1 place"}],
        )

    return fake


def test_search_without_llm_is_deterministic(auth_client):
    j = auth_client.post("/trips/search", json=BODY).json()
    assert j["agent_source"] == "deterministic"
    assert j["agent_rationale"] is None
    assert j["agent_trace"] == []
    assert j["candidate_places"][0]["id"] == "demo-coffee"


def test_search_uses_agent_when_enabled(auth_client, monkeypatch):
    monkeypatch.setattr("backend.main._llm_search_enabled", lambda: True)
    monkeypatch.setattr("backend.main.reserve_llm_search_slot", lambda: True)
    fake = _agent_returning([{"id": "demo-coffee", "name": "Demo Coffee"}])
    monkeypatch.setattr("backend.main.run_route_agent", fake)
    body = {**BODY, "arrival_time": "09:30", "arrival_date": "2026-12-01", "remaining_budget_per_person_sgd": 120.5}
    j = auth_client.post("/trips/search", json=body).json()
    assert j["agent_source"] == "agent"
    assert j["agent_rationale"] and j["agent_trace"]
    assert j["candidate_places"][0]["id"] == "demo-coffee"
    assert fake.context.arrival.isoformat() == "2026-12-01T09:30:00"
    assert fake.context.remaining_budget_per_person_sgd == 120.5


def test_agent_failure_falls_back_without_partial_results(auth_client, monkeypatch):
    monkeypatch.setattr("backend.main._llm_search_enabled", lambda: True)
    monkeypatch.setattr("backend.main.reserve_llm_search_slot", lambda: True)
    monkeypatch.setattr("backend.main.run_route_agent", AsyncMock(return_value=None))
    j = auth_client.post("/trips/search", json=BODY).json()
    assert j["agent_source"] == "deterministic"
    assert j["agent_trace"] == []
    assert j["candidate_places"][0]["id"] == "demo-coffee"


def test_agent_not_run_when_slot_unavailable_or_disabled(auth_client, monkeypatch):
    agent = AsyncMock(return_value=None)
    monkeypatch.setattr("backend.main._llm_search_enabled", lambda: True)
    monkeypatch.setattr("backend.main.run_route_agent", agent)
    monkeypatch.setattr("backend.main.reserve_llm_search_slot", lambda: False)
    assert auth_client.post("/trips/search", json=BODY).json()["agent_source"] == "deterministic"
    monkeypatch.setattr("backend.main.reserve_llm_search_slot", lambda: True)
    monkeypatch.setenv("VIBETRIP_ROUTE_AGENT_ENABLED", "false")
    assert auth_client.post("/trips/search", json=BODY).json()["agent_source"] == "deterministic"
    agent.assert_not_called()
