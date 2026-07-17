"""FastAPI entrypoint for the VibeTrip planning workflow."""

from typing import Literal

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .graph import day_builder, planner_graph
from .providers import DemoMapsProvider, get_maps_provider, suggest_cities
from .simulation import SimulationEvent, recalibrate_trip


class TripRequest(BaseModel):
    start: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    travellers: int = Field(default=4, ge=1, le=12)
    budget_per_person: int = Field(default=400, ge=0)
    dates: str = ""
    start_date: str = "2025-09-14"
    end_date: str = "2025-09-16"
    start_time: str = "08:10"
    end_time: str = "18:00"
    preferences: list[Literal["adventurous", "local-gems", "slow-mornings", "student-budget"]] = Field(default_factory=list)
    adventure_level: int = Field(default=70, ge=0, le=100)
    crowd_tolerance: Literal["low", "medium", "high"] = "medium"
    route_mode: Literal["fastest", "balanced", "scenic"] = "balanced"


class SimulationRequest(BaseModel):
    destination: str = Field(min_length=2)
    current_stop_id: str | None = None
    current_stop_title: str = "Lunch with a view"
    current_stop_index: int | None = Field(default=None, ge=0)
    event: SimulationEvent
    candidates: list[dict] = Field(default_factory=list)
    itinerary: list[dict] = Field(default_factory=list)


class RoutePlaceSearchRequest(BaseModel):
    start: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    query: str = Field(min_length=3, max_length=160)
    budget_per_person: int = Field(default=400, ge=0)
    crowd_tolerance: Literal["low", "medium", "high"] = "medium"
    route_mode: Literal["fastest", "balanced", "scenic"] = "balanced"


class RerouteRequest(BaseModel):
    start: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    start_time: str = "08:10"
    budget_per_person: int = Field(default=400, ge=0)
    crowd_tolerance: Literal["low", "medium", "high"] = "medium"
    route_mode: Literal["fastest", "balanced", "scenic"] = "balanced"
    route: dict = Field(default_factory=dict)
    stops: list[dict] = Field(default_factory=list)


app = FastAPI(title="VibeTrip Planner API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    # Vite normally runs on :5173, while the in-app preview may proxy the
    # page from another localhost port. Keep this limited to local origins.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trips/search")
async def search_route_places(request: RoutePlaceSearchRequest) -> dict:
    """Find a free-form place request near several points on the route."""
    provider = get_maps_provider()
    try:
        result = await provider.search_route_places(
            request.query,
            request.start,
            request.destination,
            request.budget_per_person,
            request.crowd_tolerance,
            request.route_mode,
        )
    except Exception as error:
        provider = DemoMapsProvider()
        result = await provider.search_route_places(
            request.query,
            request.start,
            request.destination,
            request.budget_per_person,
            request.crowd_tolerance,
            request.route_mode,
        )
        result.warning = f"Maps provider unavailable ({type(error).__name__}); showing demo matches."
    return {
        "query": request.query,
        "candidate_places": result.candidates,
        "provider": result.provider,
        "warning": result.warning,
    }


def _build_cost_breakdown(route: dict, selected_places: list[dict], travellers: int) -> dict:
    distance_km = float(route.get("distance_km") or 0)
    fuel_sgd = round(distance_km / 12 * 2.10, 2)
    tolls_sgd = round(distance_km * 0.045, 2)
    food_sgd = round(sum(float(place.get("estimated_cost_sgd") or 0) for place in selected_places if place.get("cost_type") == "food") * travellers, 2)
    known_admission_sgd = round(sum(float(place.get("estimated_cost_sgd") or 0) for place in selected_places if place.get("cost_type") == "admission"), 2)
    unknown_admissions = [place.get("name") for place in selected_places if place.get("cost_type") == "admission" and place.get("estimated_cost_sgd") is None]
    total_sgd = round(fuel_sgd + tolls_sgd + food_sgd + known_admission_sgd, 2)
    return {
        "currency": "SGD",
        "travellers": travellers,
        "estimated_total_sgd": total_sgd,
        "estimated_per_person_sgd": round(total_sgd / max(travellers, 1), 2),
        "items": [
            {"key": "fuel", "label": "Fuel", "amount_sgd": fuel_sgd, "detail": f"{round(distance_km)} km at 12 km/L and SGD 2.10/L"},
            {"key": "tolls", "label": "Tolls", "amount_sgd": tolls_sgd, "detail": "Route-distance estimate; verify local toll rates"},
            {"key": "food", "label": "Food", "amount_sgd": food_sgd, "detail": f"Google price-level estimate for {travellers} travellers"},
            {"key": "tickets", "label": "Known tickets", "amount_sgd": known_admission_sgd, "detail": "Only includes ticket prices available to the planner"},
        ],
        "unknown_admissions": unknown_admissions,
        "assumptions": ["Fuel, tolls, and food are estimates in SGD.", "Attraction admission prices must be verified from the venue or official website."],
    }


def _waypoint_places(result: dict) -> list[dict]:
    """Return itinerary places in driving order, not recommendation-score order."""
    candidates_by_id = {
        candidate.get("id"): candidate
        for candidate in result.get("candidate_places", [])
        if candidate.get("id")
    }
    places = []
    seen_ids = set()
    for item in result.get("itinerary", []):
        place_id = item.get("place_id")
        candidate = candidates_by_id.get(place_id)
        if place_id and place_id not in seen_ids and candidate and candidate.get("location"):
            places.append(candidate)
            seen_ids.add(place_id)
    return places


@app.post("/trips/plan")
async def plan_trip(request: TripRequest) -> dict:
    """Run the planner and return a resumable draft plan."""
    provider = get_maps_provider()
    try:
        provider_result = await provider.plan_trip(request.start, request.destination, request.budget_per_person, request.crowd_tolerance, request.start_time, request.route_mode)
    except Exception as error:
        fallback = DemoMapsProvider()
        provider = fallback
        provider_result = await fallback.plan_trip(request.start, request.destination, request.budget_per_person, request.crowd_tolerance, request.start_time, request.route_mode)
        provider_result.warning = f"Maps provider unavailable ({type(error).__name__}); showing demo candidates."
    state = request.model_dump() | {"route": provider_result.route, "candidate_places": provider_result.candidates}
    result = planner_graph.invoke(state)
    reroute_warning = None
    for _ in range(3):
        waypoint_places = _waypoint_places(result)
        if not waypoint_places:
            break
        try:
            updated_route = await provider.reroute_with_stops(
                request.start,
                request.destination,
                result["route"],
                waypoint_places,
                request.start_time,
            )
            previous_waypoint_ids = [place.get("id") for place in waypoint_places]
            result = day_builder({**result, "route": updated_route})
            final_waypoint_ids = [place.get("id") for place in _waypoint_places(result)]
            if final_waypoint_ids == previous_waypoint_ids:
                break
        except Exception as error:
            reroute_warning = f"Selected stops could not be added as route waypoints ({type(error).__name__}); the baseline route is still available."
            break
    warnings = [
        warning
        for warning in (
            provider_result.warning,
            result.get("route", {}).get("schedule_warning"),
            reroute_warning,
        )
        if warning
    ]
    return {
        "start": result["start"],
        "destination": result["destination"],
        "route": result["route"],
        "vibe_profile": result["vibe_profile"],
        "detours": result["detours"],
        "candidate_places": result.get("candidate_places", []),
        "selected_places": result.get("selected_places", []),
        "itinerary": result["itinerary"],
        "confidence": result["confidence"],
        "cost_breakdown": _build_cost_breakdown(result["route"], result.get("selected_places", []), request.travellers),
        "provider": provider_result.provider,
        "warning": " ".join(warnings) or None,
    }


@app.post("/trips/reroute")
async def reroute_trip(request: RerouteRequest) -> dict:
    """Recompute map geometry immediately after a draft stop edit."""
    provider = get_maps_provider()
    try:
        if request.stops:
            route = await provider.reroute_with_stops(
                request.start,
                request.destination,
                request.route,
                request.stops,
                request.start_time,
            )
        else:
            provider_result = await provider.plan_trip(
                request.start,
                request.destination,
                request.budget_per_person,
                request.crowd_tolerance,
                request.start_time,
                request.route_mode,
            )
            route = provider_result.route
        return {"route": route, "provider": provider.__class__.__name__.replace("MapsProvider", "").lower() or "demo", "warning": None}
    except Exception as error:
        fallback = DemoMapsProvider()
        if request.stops:
            route = await fallback.reroute_with_stops(request.start, request.destination, request.route, request.stops, request.start_time)
        else:
            route = (await fallback.plan_trip(request.start, request.destination, request.budget_per_person, request.crowd_tolerance, request.start_time, request.route_mode)).route
        return {
            "route": route,
            "provider": "demo",
            "warning": f"Live route recalculation unavailable ({type(error).__name__}); showing the draft route geometry.",
        }


@app.get("/places/autocomplete")
async def places_autocomplete(q: str = Query(min_length=2, max_length=100)) -> dict:
    try:
        return {"suggestions": await suggest_cities(q)}
    except Exception:
        return {"suggestions": []}


@app.post("/trips/simulate")
def simulate_trip(request: SimulationRequest) -> dict:
    return recalibrate_trip(
        itinerary=request.itinerary,
        candidates=request.candidates,
        current_stop_id=request.current_stop_id,
        current_stop_title=request.current_stop_title,
        current_stop_index=request.current_stop_index,
        event=request.event,
        destination=request.destination,
    )
