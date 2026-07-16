"""FastAPI entrypoint for the VibeTrip planning workflow."""

from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .graph import planner_graph
from .providers import DemoMapsProvider, get_maps_provider
from .simulation import SimulationEvent, recalibrate_trip


class TripRequest(BaseModel):
    start: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    travellers: int = Field(default=4, ge=1, le=12)
    budget_per_person: int = Field(default=400, ge=0)
    dates: str = ""
    preferences: list[Literal["adventurous", "local-gems", "slow-mornings", "student-budget"]] = []
    crowd_tolerance: Literal["low", "medium", "high"] = "medium"


class SimulationRequest(BaseModel):
    destination: str = Field(min_length=2)
    current_stop_id: str | None = None
    current_stop_title: str = "Lunch with a view"
    event: SimulationEvent
    candidates: list[dict] = Field(default_factory=list)
    itinerary: list[dict] = Field(default_factory=list)


app = FastAPI(title="VibeTrip Planner API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trips/plan")
async def plan_trip(request: TripRequest) -> dict:
    """Run the planner and return a resumable draft plan."""
    provider = get_maps_provider()
    try:
        provider_result = await provider.plan_trip(request.start, request.destination, request.budget_per_person, request.crowd_tolerance)
    except Exception as error:
        fallback = DemoMapsProvider()
        provider_result = await fallback.plan_trip(request.start, request.destination, request.budget_per_person, request.crowd_tolerance)
        provider_result.warning = f"Maps provider unavailable ({type(error).__name__}); showing demo candidates."
    state = request.model_dump() | {"route": provider_result.route, "candidate_places": provider_result.candidates}
    result = planner_graph.invoke(state)
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
        "provider": provider_result.provider,
        "warning": provider_result.warning,
    }


@app.post("/trips/simulate")
def simulate_trip(request: SimulationRequest) -> dict:
    return recalibrate_trip(
        itinerary=request.itinerary,
        candidates=request.candidates,
        current_stop_id=request.current_stop_id,
        current_stop_title=request.current_stop_title,
        event=request.event,
        destination=request.destination,
    )
