"""FastAPI entrypoint for the VibeTrip planning workflow."""

from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .graph import planner_graph


class TripRequest(BaseModel):
    start: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    travellers: int = Field(default=4, ge=1, le=12)
    budget_per_person: int = Field(default=400, ge=0)
    dates: str = ""
    preferences: list[Literal["adventurous", "local-gems", "slow-mornings", "student-budget"]] = []


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
def plan_trip(request: TripRequest) -> dict:
    """Run the planner and return a resumable draft plan."""
    result = planner_graph.invoke(request.model_dump())
    return {
        "start": result["start"],
        "destination": result["destination"],
        "route": result["route"],
        "vibe_profile": result["vibe_profile"],
        "detours": result["detours"],
        "itinerary": result["itinerary"],
        "confidence": result["confidence"],
    }
