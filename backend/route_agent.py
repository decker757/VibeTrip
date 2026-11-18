"""Route assistant agent: an LLM picks tools to find replacement stops for one leg.

Who owns what:
- The agent (LLM) decides which tools to call and with what text: the search
  query and category, which places to check, and the final shortlist with a
  one-sentence rationale.
- Code owns correctness. The route segment, budget, crowd tolerance and route
  mode come from the request, never from the model. Opening hours at arrival
  are enforced on the final shortlist even if the agent never checked them,
  ids the agent never saw are dropped, and searches and steps are capped.
  Any failure returns None so the caller runs the deterministic search.

Graph:  START -> agent --(tool calls)--> tools -> agent ...
                  agent --(SubmitShortlist / no tool call / step cap)--> END
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, ValidationError

from .opening_hours import opening_status_at
from .providers import CATEGORY_FILTER_PHRASES, RouteGeometry, _extract_location_hint
from .recommender import get_chat_model

logger = logging.getLogger(__name__)

MAX_SEARCHES = 3
MAX_STEPS = 8
MAX_SHORTLIST = 4
FILL_STOP_MINUTES = 30  # fill mode: how long a suggested extra stop takes
DEFAULT_TIMEOUT_SECONDS = 20.0

SYSTEM_PROMPT = f"""You help a road-tripper replace one stop on a single leg of their drive.
- Choose only place ids returned by your tools. Never invent places, ids, prices or opening hours.
- The route segment, opening hours and budget are enforced by code: places outside this leg never
  appear in results, and places closed at arrival are removed from your shortlist.
- Use CheckOpenAtArrival and CheckBudget when they matter to the request. Each check's answer is
  final: missing hours or prices will not appear on a second call, so never repeat a check.
- If nothing fits, broaden the query or change the category and search again (at most {MAX_SEARCHES} searches).
- Finish by calling SubmitShortlist with at most {MAX_SHORTLIST} ids, best first, and one sentence of rationale."""

_FILL_RULES = SYSTEM_PROMPT.split("\n", 1)[1]
FILL_SYSTEM_PROMPT = (
    "You help a road-tripper add one stop to a leg of their drive. They have {spare} spare minutes; "
    f"the stop takes about {FILL_STOP_MINUTES} minutes plus its detour. Places whose detour does not fit are removed by code.\n"
    + _FILL_RULES
)


# --- Tool argument schemas: the only things the LLM is allowed to supply ---

class SearchPlaces(BaseModel):
    """Search for places along the current leg of the route."""
    query: str = Field(description="Free-text place search, e.g. 'quiet cafe with a view'.")
    category: Literal["restaurant", "cafe", "fuel", "scenic", "other"]


class CheckOpenAtArrival(BaseModel):
    """Check whether places are open when the traveller would arrive."""
    place_ids: list[str]


class CheckBudget(BaseModel):
    """Compare places' cost with the current stop and the remaining budget."""
    place_ids: list[str]


class SubmitShortlist(BaseModel):
    """Finish with the best replacement places, best first."""
    place_ids: list[str] = Field(description=f"At most {MAX_SHORTLIST} ids returned by SearchPlaces.")
    rationale: str = Field(description="One sentence explaining the choice.")


TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    schema.__name__: schema for schema in (SearchPlaces, CheckOpenAtArrival, CheckBudget, SubmitShortlist)
}


@dataclass
class RouteAgentContext:
    """Request facts fixed by the API. The agent can read them but not change them."""
    start: str
    destination: str
    budget_per_person: int
    crowd_tolerance: str
    route_mode: str
    segment_start_progress_km: float | None
    segment_end_progress_km: float | None
    target_progress_km: float | None
    arrival: datetime | None
    current_stop_cost_sgd: float | None
    remaining_budget_per_person_sgd: float | None
    selected_stop_title: str
    previous_stop_title: str
    next_stop_title: str
    query: str
    mode: Literal["replace", "fill"] = "replace"
    spare_minutes: int | None = None  # fill mode only


@dataclass
class RouteAgentResult:
    candidates: list[dict[str, Any]]
    rationale: str
    trace: list[dict[str, Any]]


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    seen_candidates: dict[str, dict[str, Any]]
    trace: list[dict[str, Any]]
    step_count: int
    search_count: int
    shortlist_ids: list[str]
    rationale: str


@dataclass
class ToolOutcome:
    content: str  # what the model reads
    summary: str  # what the traveller sees in the step trace
    found: list[dict[str, Any]] = field(default_factory=list)


# --- Tool implementations: deterministic code wrapping the provider ---

class RouteAgentTools:
    """Runs tool calls with the request context, never trusting the model for facts."""

    def __init__(self, context: RouteAgentContext, provider: Any):
        self.context = context
        self.provider = provider
        self._geometry: RouteGeometry | None = None

    async def search_places(self, args: SearchPlaces) -> ToolOutcome:
        ctx = self.context
        if self._geometry is None:  # one route lookup per run, shared by every search
            self._geometry = await self.provider.route_geometry(ctx.start, ctx.destination, ctx.route_mode)
        # The locality comes from the traveller's own words, so the model cannot invent one.
        location_hint = _extract_location_hint(ctx.query)
        text_query = args.query
        if location_hint and location_hint not in text_query.lower():
            text_query = f"{text_query} near {location_hint}"
        results = await self.provider.search_places_text(
            self._geometry, text_query, CATEGORY_FILTER_PHRASES[args.category], location_hint,
            ctx.budget_per_person, ctx.crowd_tolerance, ctx.route_mode,
            ctx.segment_start_progress_km, ctx.segment_end_progress_km, ctx.target_progress_km,
        )
        content = json.dumps([_compact(place) for place in results]) if results else (
            "No places matched in this leg. Try a broader query or another category."
        )
        return ToolOutcome(content, f"Searched '{args.query}' ({args.category}) → {len(results)} in this leg", results)

    def check_open_at_arrival(self, args: CheckOpenAtArrival, seen: dict[str, dict[str, Any]]) -> ToolOutcome:
        return _per_place_outcome(args.place_ids, seen, lambda place: _open_status(place, self.context.arrival))

    def check_budget(self, args: CheckBudget, seen: dict[str, dict[str, Any]]) -> ToolOutcome:
        ctx = self.context
        return _per_place_outcome(
            args.place_ids, seen,
            lambda place: _budget_status(place, ctx.current_stop_cost_sgd, ctx.remaining_budget_per_person_sgd),
        )


def _compact(place: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": place.get("id"),
        "name": place.get("name"),
        "category": place.get("category"),
        "rating": place.get("rating"),
        "detour_minutes": place.get("detour_minutes"),
        "cost": place.get("cost_label") or place.get("price_label"),
        "crowd_risk": place.get("crowd_risk"),
    }


def _per_place_outcome(
    place_ids: list[str], seen: dict[str, dict[str, Any]], describe: Callable[[dict[str, Any]], str],
) -> ToolOutcome:
    lines = [
        f"{seen[place_id].get('name', place_id)}: {describe(seen[place_id])}" if place_id in seen
        else f"{place_id}: not found; use an id from SearchPlaces"
        for place_id in place_ids
    ]
    text = "; ".join(lines) or "No place ids given."
    return ToolOutcome(text, text)


def _open_status(place: dict[str, Any], arrival: datetime | None) -> str:
    status = opening_status_at(place, arrival) if arrival else None
    return {True: "open", False: "closed", None: "no opening hours on record (not excluded)"}[status]


def _budget_status(place: dict[str, Any], current_cost: float | None, remaining: float | None) -> str:
    cost = place.get("estimated_cost_sgd")
    if cost is None:
        return "no price on record, so budget can't be checked"
    if current_cost is None:
        versus_current = "current stop's cost is unknown"
    elif cost == current_cost:
        versus_current = "same cost as current stop"
    else:
        versus_current = f"SGD {abs(cost - current_cost):.0f} {'cheaper' if cost < current_cost else 'more'} than current stop"
    if remaining is None:
        versus_budget = "no remaining budget given"
    else:
        # The remaining budget already pays for the current stop, so only the extra cost counts.
        extra_cost = cost - current_cost if current_cost is not None else cost
        versus_budget = f"{'within' if extra_cost <= remaining else 'over'} remaining SGD {remaining:.0f}"
    return f"{versus_current}; {versus_budget}"


# --- Graph nodes and routing ---

def _runtime(config: RunnableConfig) -> tuple[Any, RouteAgentTools]:
    configurable = config["configurable"]
    return configurable["model"], configurable["tools"]


def _with_trace_entry(trace: list[dict[str, Any]], tool: str, summary: str) -> list[dict[str, Any]]:
    return [*trace, {"step": len(trace) + 1, "tool": tool, "summary": summary}]


def _valid_submission(message: AIMessage) -> SubmitShortlist | None:
    """The shortlist from a well-formed SubmitShortlist call; malformed ones go to tools for a retry."""
    for call in message.tool_calls:
        if call["name"] == "SubmitShortlist":
            try:
                return SubmitShortlist.model_validate(call["args"])
            except ValidationError:
                continue
    return None


async def agent_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Ask the model for its next move; record the shortlist if it submits one."""
    model, _ = _runtime(config)
    if state["step_count"] == MAX_STEPS - 1:
        # Last step: only SubmitShortlist is offered, so the run always ends with a decision.
        model = config["configurable"]["final_model"]
    response = await model.ainvoke(state["messages"])
    update: dict[str, Any] = {"messages": [response], "step_count": state["step_count"] + 1}
    shortlist = _valid_submission(response)
    if shortlist:
        update["shortlist_ids"] = shortlist.place_ids
        update["rationale"] = shortlist.rationale
        update["trace"] = _with_trace_entry(state["trace"], "SubmitShortlist", f"Shortlisted {len(shortlist.place_ids)} place(s)")
    return update


def route_after_agent(state: AgentState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    if not last.tool_calls or _valid_submission(last) or state["step_count"] >= MAX_STEPS:
        return END
    return "tools"


async def tools_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Execute every tool call from the last model turn and answer each one."""
    _, tools = _runtime(config)
    seen = dict(state["seen_candidates"])
    trace = state["trace"]
    search_count = state["search_count"]
    replies: list[ToolMessage] = []
    for call in state["messages"][-1].tool_calls:
        name = call["name"]
        try:
            args = TOOL_SCHEMAS[name].model_validate(call["args"])
        except (KeyError, ValidationError) as error:
            outcome = ToolOutcome(f"Invalid call to {name}: {error}", f"Rejected an invalid {name} call")
        else:
            if name == "SearchPlaces" and search_count >= MAX_SEARCHES:
                outcome = ToolOutcome(
                    f"Search limit of {MAX_SEARCHES} reached. Submit a shortlist from the places you have.",
                    "Search limit reached; no further searches",
                )
            elif name == "SearchPlaces":
                search_count += 1
                outcome = await tools.search_places(args)
            elif name == "CheckOpenAtArrival":
                outcome = tools.check_open_at_arrival(args, seen)
            else:  # CheckBudget; a valid SubmitShortlist ends the graph before reaching this node
                outcome = tools.check_budget(args, seen)
        for place in outcome.found:
            seen.setdefault(place["id"], place)
        trace = _with_trace_entry(trace, name, outcome.summary)
        replies.append(ToolMessage(content=outcome.content, tool_call_id=call["id"]))
    return {"messages": replies, "seen_candidates": seen, "trace": trace, "search_count": search_count}


def build_route_agent_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    return workflow.compile()


ROUTE_AGENT_GRAPH = build_route_agent_graph()


# --- Entry point and post-processing ---

def fits_spare(place: dict[str, Any], spare_minutes: int) -> bool:
    """detour_minutes is already the out-and-back time, so it is counted once."""
    return float(place.get("detour_minutes") or 0) + FILL_STOP_MINUTES <= spare_minutes


def _request_message(ctx: RouteAgentContext) -> HumanMessage:
    arrival = ctx.arrival.strftime("%A %H:%M") if ctx.arrival else "unknown"
    task = (
        f"Adding a stop between {ctx.previous_stop_title} and {ctx.next_stop_title}; {ctx.spare_minutes} spare minutes"
        if ctx.mode == "fill"
        else f"Replacing: {ctx.selected_stop_title} (between {ctx.previous_stop_title} and {ctx.next_stop_title})"
    )
    return HumanMessage(content=(
        f'Traveller request: "{ctx.query}"\n'
        f"{task}\n"
        f"Arrival at this stop: {arrival}\n"
        f"Budget per person: SGD {ctx.budget_per_person}; crowd tolerance: {ctx.crowd_tolerance}; route mode: {ctx.route_mode}"
    ))


def _system_prompt(ctx: RouteAgentContext) -> str:
    return FILL_SYSTEM_PROMPT.format(spare=ctx.spare_minutes) if ctx.mode == "fill" else SYSTEM_PROMPT


def _initial_state(ctx: RouteAgentContext) -> AgentState:
    return {
        "messages": [SystemMessage(content=_system_prompt(ctx)), _request_message(ctx)],
        "seen_candidates": {},
        "trace": [],
        "step_count": 0,
        "search_count": 0,
        "shortlist_ids": [],
        "rationale": "",
    }


def _validated_candidates(shortlist_ids: list[str], seen: dict[str, dict[str, Any]], ctx: RouteAgentContext) -> list[dict[str, Any]]:
    """Agent's picks first (seen, not closed, and in fill mode fitting the spare time), then other seen places that pass the same checks.

    Each entry carries ``agent_pick`` so the UI can tell the shortlist from the extras."""
    arrival = ctx.arrival
    must_fit = ctx.mode == "fill" and ctx.spare_minutes is not None

    def allowed(place_id: str) -> bool:
        if place_id not in seen or (arrival and opening_status_at(seen[place_id], arrival) is False):
            return False
        return not must_fit or fits_spare(seen[place_id], ctx.spare_minutes)

    shortlist = [place_id for place_id in dict.fromkeys(shortlist_ids) if allowed(place_id)][:MAX_SHORTLIST]
    if not shortlist:
        return []
    others = [place_id for place_id in seen if place_id not in shortlist and allowed(place_id)]
    return [{**seen[place_id], "agent_pick": place_id in shortlist} for place_id in shortlist + others]


def _agent_timeout_seconds() -> float:
    try:
        return float(os.getenv("VIBETRIP_AGENT_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


async def run_route_agent(context: RouteAgentContext, provider: Any, model: Any = None) -> RouteAgentResult | None:
    """Run the agent; None means the caller should fall back to the deterministic search."""
    try:
        chat_model = model if model is not None else get_chat_model()
        config = {"configurable": {
            "model": chat_model.bind_tools(list(TOOL_SCHEMAS.values())),
            "final_model": chat_model.bind_tools([SubmitShortlist], tool_choice="SubmitShortlist"),
            "tools": RouteAgentTools(context, provider),
        }}
        final = await asyncio.wait_for(ROUTE_AGENT_GRAPH.ainvoke(_initial_state(context), config), _agent_timeout_seconds())
    except Exception:
        logger.warning("Route agent failed; falling back to deterministic search", exc_info=True)
        return None
    candidates = _validated_candidates(final["shortlist_ids"], final["seen_candidates"], context)
    if not candidates:
        return None
    return RouteAgentResult(candidates=candidates, rationale=final["rationale"], trace=final["trace"])
