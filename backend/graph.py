"""Small, serializable LangGraph workflow for a VibeTrip draft plan.

The nodes are deliberately provider-agnostic for the MVP. Real route, maps,
weather, and recommendation providers can be added behind each node without
changing the API contract or the frontend's state model.
"""

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class PlannerState(TypedDict, total=False):
    start: str
    destination: str
    travellers: int
    budget_per_person: int
    dates: str
    preferences: list[str]
    route: dict[str, Any]
    vibe_profile: dict[str, Any]
    candidate_places: list[dict[str, Any]]
    selected_places: list[dict[str, Any]]
    detours: list[dict[str, Any]]
    itinerary: list[dict[str, Any]]
    confidence: int


def route_scout(state: PlannerState) -> PlannerState:
    """Find a practical baseline route and leave room for future map APIs."""
    return {
        **state,
        "route": {
            "distance_km": 348,
            "drive_minutes": 229,
            "summary": f"{state['start']} to {state['destination']}",
            "stops_needed": ["fuel", "bathroom", "meal"],
        },
    }


def vibe_matcher(state: PlannerState) -> PlannerState:
    """Infer a lightweight archetype from the user's explicit preferences."""
    preferences = set(state.get("preferences", []))
    adventurous = "adventurous" in preferences or "local-gems" in preferences
    return {
        **state,
        "vibe_profile": {
            "archetype": "Curious, not rushed" if adventurous else "Easygoing explorer",
            "adventure_score": 70 if adventurous else 48,
            "budget_mode": "student-friendly",
            "buffer_percent": 20,
        },
    }


def detour_reviewer(state: PlannerState) -> PlannerState:
    """Score candidate stops against time, budget, and the inferred profile."""
    candidates = state.get("candidate_places") or [{
        "id": "fallback-lunch",
        "name": "The Lobster Shack",
        "address": "Mystic, CT",
        "category": "Restaurant",
        "detour_minutes": 12,
        "enjoyment_score": 88,
        "reason": "A high-value meal stop with a short route deviation.",
        "open_now": True,
    }]
    ranked = sorted(candidates, key=lambda item: item.get("enjoyment_score", 0), reverse=True)
    selected = [item for item in ranked if item.get("open_now", True)][:2]
    return {**state, "candidate_places": ranked, "selected_places": selected, "detours": selected}


def day_builder(state: PlannerState) -> PlannerState:
    """Turn the route and accepted detours into a buffer-aware day plan."""
    meal_stop = next((item for item in state.get("selected_places", []) if "restaurant" in item.get("category", "").lower()), None)
    meal_name = meal_stop.get("name", "Lunch with a view") if meal_stop else "Lunch with a view"
    return {
        **state,
        "confidence": 94,
        "itinerary": [
            {"time": "08:10", "title": "Coffee + stretch", "kind": "coffee", "duration_min": 25},
            {"time": "10:55", "title": "Fuel up", "kind": "fuel", "duration_min": 15},
            {"time": "12:30", "title": meal_name, "kind": "meal", "duration_min": 55, "place_id": meal_stop.get("id") if meal_stop else None},
            {"time": "15:40", "title": "Check-in", "kind": "stay", "duration_min": 0},
        ],
    }


def build_planner_graph():
    """Compile the workflow once at application startup."""
    workflow = StateGraph(PlannerState)
    workflow.add_node("route_scout", route_scout)
    workflow.add_node("vibe_matcher", vibe_matcher)
    workflow.add_node("detour_reviewer", detour_reviewer)
    workflow.add_node("day_builder", day_builder)
    workflow.add_edge(START, "route_scout")
    workflow.add_edge("route_scout", "vibe_matcher")
    workflow.add_edge("vibe_matcher", "detour_reviewer")
    workflow.add_edge("detour_reviewer", "day_builder")
    workflow.add_edge("day_builder", END)
    return workflow.compile()


planner_graph = build_planner_graph()
