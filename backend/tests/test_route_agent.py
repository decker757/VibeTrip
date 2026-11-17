import asyncio
from datetime import datetime

from langchain_core.messages import AIMessage, ToolMessage

from backend.providers import DemoMapsProvider
from backend.route_agent import MAX_SEARCHES, MAX_STEPS, RouteAgentContext, _budget_status, run_route_agent
from backend.tests.fakes import ScriptedChatModel

ARRIVAL = datetime(2026, 11, 20, 10, 0)  # a Friday; Google weekday 5


def ai_tool(name, args, id="1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id}])


def ctx(segment=(0, 100), arrival=ARRIVAL, target=50, current_cost=None, remaining=None, query="somewhere quieter"):
    return RouteAgentContext(
        start="A",
        destination="B",
        budget_per_person=400,
        crowd_tolerance="medium",
        route_mode="balanced",
        segment_start_progress_km=segment[0],
        segment_end_progress_km=segment[1],
        target_progress_km=target,
        arrival=arrival,
        current_stop_cost_sgd=current_cost,
        remaining_budget_per_person_sgd=remaining,
        selected_stop_title="Coffee stop",
        previous_stop_title="Start",
        next_stop_title="Fuel stop",
        query=query,
    )


class CountingDemoProvider(DemoMapsProvider):
    def __init__(self):
        self.geometry_calls = 0
        self.search_calls = 0

    async def route_geometry(self, *args, **kwargs):
        self.geometry_calls += 1
        return await super().route_geometry(*args, **kwargs)

    async def search_places_text(self, *args, **kwargs):
        self.search_calls += 1
        return await super().search_places_text(*args, **kwargs)


class EveningCoffeeProvider(DemoMapsProvider):
    """Demo provider whose coffee stop only opens on Friday evenings."""

    async def search_places_text(self, *args, **kwargs):
        results = await super().search_places_text(*args, **kwargs)
        evening = {"periods": [{"open": {"day": 5, "hour": 18, "minute": 0}, "close": {"day": 5, "hour": 22, "minute": 0}}]}
        return [{**place, "opening_hours": evening} if place["id"] == "demo-coffee" else place for place in results]


async def test_happy_path_returns_shortlist_and_trace():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "quiet cafe", "category": "cafe"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"], "rationale": "Quiet and on the way."}, "2")])
    r = await run_route_agent(ctx(segment=(0, 100)), DemoMapsProvider(), model)
    assert r.candidates[0]["id"] == "demo-coffee" and r.rationale == "Quiet and on the way."
    assert [t["tool"] for t in r.trace] == ["SearchPlaces", "SubmitShortlist"]
    assert [t["step"] for t in r.trace] == [1, 2]


async def test_search_results_reach_the_model_as_tool_messages():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "quiet cafe", "category": "cafe"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"], "rationale": "x"}, "2")])
    await run_route_agent(ctx(segment=(0, 100)), DemoMapsProvider(), model)
    tool_message = model.calls[1][-1]
    assert isinstance(tool_message, ToolMessage) and tool_message.tool_call_id == "1"
    assert "demo-coffee" in tool_message.content


async def test_unseen_ids_are_dropped():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "cafe", "category": "cafe"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["made-up", "demo-coffee"], "rationale": "x"}, "2")])
    r = await run_route_agent(ctx(segment=(0, 100)), DemoMapsProvider(), model)
    assert [c["id"] for c in r.candidates] == ["demo-coffee"]


async def test_other_seen_candidates_follow_the_shortlist():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "anything", "category": "other"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-lunch", "demo-lunch"], "rationale": "x"}, "2")])
    r = await run_route_agent(ctx(segment=(100, 210), target=None), DemoMapsProvider(), model)
    assert [c["id"] for c in r.candidates] == ["demo-lunch", "demo-fuel", "demo-attraction"]
    assert [c["agent_pick"] for c in r.candidates] == [True, False, False]


async def test_closed_at_arrival_dropped_even_without_check():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "cafe", "category": "cafe"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"], "rationale": "x"}, "2")])
    assert await run_route_agent(ctx(segment=(0, 100)), EveningCoffeeProvider(), model) is None


async def test_open_check_reports_closed_places():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "cafe", "category": "cafe"}),
                               ai_tool("CheckOpenAtArrival", {"place_ids": ["demo-coffee"]}, "2"),
                               ai_tool("SubmitShortlist", {"place_ids": [], "rationale": "x"}, "3")])
    await run_route_agent(ctx(segment=(0, 100)), EveningCoffeeProvider(), model)
    assert "The Coffee Exchange: closed" in model.calls[2][-1].content


async def test_search_cap():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": f"q{i}", "category": "other"}, str(i)) for i in range(4)]
                              + [ai_tool("SubmitShortlist", {"place_ids": ["demo-fuel"], "rationale": "x"}, "9")])
    provider = CountingDemoProvider()
    r = await run_route_agent(ctx(segment=(100, 210)), provider, model)
    assert provider.search_calls == MAX_SEARCHES == 3 and provider.geometry_calls == 1
    assert "limit" in r.trace[3]["summary"].lower()


async def test_step_cap_returns_none():
    model = ScriptedChatModel([ai_tool("CheckBudget", {"place_ids": []}, str(i)) for i in range(10)])
    assert await run_route_agent(ctx(), DemoMapsProvider(), model) is None
    assert len(model.calls) == MAX_STEPS == 8


async def test_no_tool_call_ends_without_shortlist():
    model = ScriptedChatModel([AIMessage(content="I could not find anything.")])
    assert await run_route_agent(ctx(), DemoMapsProvider(), model) is None


async def test_model_exception_returns_none():
    class Broken(ScriptedChatModel):
        def _generate(self, *a, **k): raise RuntimeError("down")
    assert await run_route_agent(ctx(), DemoMapsProvider(), Broken([])) is None


async def test_timeout_returns_none(monkeypatch):
    monkeypatch.setenv("VIBETRIP_AGENT_TIMEOUT_SECONDS", "0.05")

    class Slow(ScriptedChatModel):
        async def _agenerate(self, *a, **k):
            await asyncio.sleep(1)
    assert await run_route_agent(ctx(), DemoMapsProvider(), Slow([])) is None


async def test_invalid_tool_arguments_are_reported_to_the_model():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "cafe", "category": "bar"}),
                               ai_tool("SearchPlaces", {"query": "cafe", "category": "cafe"}, "2"),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"], "rationale": "x"}, "3")])
    r = await run_route_agent(ctx(segment=(0, 100)), DemoMapsProvider(), model)
    assert "invalid" in model.calls[1][-1].content.lower()
    assert [c["id"] for c in r.candidates] == ["demo-coffee"]


async def test_missing_arrival_and_progress_still_runs():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "cafe", "category": "cafe"}),
                               ai_tool("CheckOpenAtArrival", {"place_ids": ["demo-coffee"]}, "2"),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"], "rationale": "x"}, "3")])
    r = await run_route_agent(ctx(segment=(None, None), arrival=None, target=None), DemoMapsProvider(), model)
    assert r is not None and "unknown" in r.trace[1]["summary"]


async def test_budget_summary():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "seafood lunch", "category": "restaurant"}),
                               ai_tool("CheckBudget", {"place_ids": ["demo-lunch"]}, "2"),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-lunch"], "rationale": "x"}, "3")])
    r = await run_route_agent(ctx(segment=(200, 250), current_cost=30, remaining=140), DemoMapsProvider(), model)
    assert r.trace[1]["summary"] == "The Lobster Shack: SGD 8 cheaper than current stop; within remaining SGD 140"


async def test_budget_summary_unknown_without_budget_inputs():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "seafood lunch", "category": "restaurant"}),
                               ai_tool("CheckBudget", {"place_ids": ["demo-lunch"]}, "2"),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-lunch"], "rationale": "x"}, "3")])
    r = await run_route_agent(ctx(segment=(200, 250)), DemoMapsProvider(), model)
    assert r.trace[1]["summary"] == "The Lobster Shack: unknown vs current stop; unknown vs remaining budget"


# Remaining budget already includes the stop being replaced, so only the extra cost counts.
def test_budget_within_remaining_uses_extra_cost_over_current_stop():
    assert _budget_status({"estimated_cost_sgd": 150}, 100, 60) == "SGD 50 more than current stop; within remaining SGD 60"


def test_budget_over_remaining_uses_extra_cost_over_current_stop():
    assert _budget_status({"estimated_cost_sgd": 200}, 100, 60) == "SGD 100 more than current stop; over remaining SGD 60"


def test_budget_without_current_cost_compares_full_cost():
    assert _budget_status({"estimated_cost_sgd": 70}, None, 60) == "unknown vs current stop; over remaining SGD 60"


async def test_malformed_submit_gets_a_retry():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "cafe", "category": "cafe"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"]}, "2"),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"], "rationale": "Calm stop."}, "3")])
    r = await run_route_agent(ctx(segment=(0, 100)), DemoMapsProvider(), model)
    assert r is not None and r.rationale == "Calm stop." and [c["id"] for c in r.candidates] == ["demo-coffee"]
    retry_prompt = model.calls[2][-1]
    assert isinstance(retry_prompt, ToolMessage) and retry_prompt.tool_call_id == "2" and "invalid" in retry_prompt.content.lower()
