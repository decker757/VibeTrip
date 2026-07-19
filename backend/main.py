"""FastAPI entrypoint for the VibeTrip planning workflow."""

from collections import defaultdict, deque
from datetime import date
import os
import time
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .graph import day_builder, planner_graph
from .auth import SESSION_COOKIE, auth_repository, get_current_user, issue_session, public_user
from .media import MEDIA_ROOT, MAX_TRIP_MEDIA, save_upload
from .okf import okf_profile_exporter
from .providers import DemoMapsProvider, get_maps_provider, place_details, suggest_cities
from .search_intent import parse_place_search_intent
from .simulation import SimulationEvent, recalibrate_trip
from .storage import OWNER_ID, context_event_repository, trip_repository


class ProfileContext(BaseModel):
    name: str = Field(default="VibeTrip traveller", min_length=1, max_length=120)
    home_base: str = Field(default="Singapore", min_length=2, max_length=120)
    exchange_student: bool = True


class TripRequest(BaseModel):
    start: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    travellers: int = Field(default=4, ge=1, le=12)
    budget_per_person: int = Field(default=400, ge=0)
    dates: str = ""
    start_date: str = Field(default_factory=lambda: date.today().isoformat())
    end_date: str = Field(default_factory=lambda: date.today().isoformat())
    start_time: str = "08:10"
    end_time: str = "18:00"
    preferences: list[Literal["adventurous", "local-gems", "slow-mornings"]] = Field(default_factory=list)
    adventure_level: int = Field(default=70, ge=0, le=100)
    crowd_tolerance: Literal["low", "medium", "high"] = "medium"
    route_mode: Literal["fastest", "balanced", "scenic"] = "balanced"
    profile: ProfileContext = Field(default_factory=ProfileContext)


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
    segment_start_progress_km: float | None = Field(default=None, ge=0)
    segment_end_progress_km: float | None = Field(default=None, ge=0)
    target_progress_km: float | None = Field(default=None, ge=0)
    selected_stop_title: str = ""
    previous_stop_title: str = ""
    next_stop_title: str = ""


class RerouteRequest(BaseModel):
    start: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    start_time: str = "08:10"
    budget_per_person: int = Field(default=400, ge=0)
    crowd_tolerance: Literal["low", "medium", "high"] = "medium"
    route_mode: Literal["fastest", "balanced", "scenic"] = "balanced"
    route: dict = Field(default_factory=dict)
    stops: list[dict] = Field(default_factory=list)


class SaveTripRequest(BaseModel):
    id: str | None = None
    owner_id: str = OWNER_ID
    title: str = Field(min_length=2, max_length=140)
    start: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    route_mode: Literal["fastest", "balanced", "scenic"] = "balanced"
    adventure_level: int = Field(default=70, ge=0, le=100)
    budget_per_person: int = Field(default=400, ge=0)
    travellers: int = Field(default=4, ge=1, le=12)
    start_date: str = ""
    end_date: str = ""
    start_time: str = "08:10"
    end_time: str = "18:00"
    preferences: list[str] = Field(default_factory=list)
    route: dict = Field(default_factory=dict)
    itinerary: list[dict] = Field(default_factory=list)
    candidate_places: list[dict] = Field(default_factory=list)
    cost_breakdown: dict = Field(default_factory=dict)
    media: list[dict] = Field(default_factory=list)
    post_caption: str = Field(default="", max_length=2000)
    is_public: bool = False
    is_completed: bool = False


class VisibilityRequest(BaseModel):
    is_public: bool


class PublishTripRequest(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    post_caption: str = Field(default="", max_length=2000)
    media_captions: dict[str, str] = Field(default_factory=dict)


class UserProfileRequest(ProfileContext):
    owner_id: str = OWNER_ID
    preferences: list[str] = Field(default_factory=list)
    adventure_level: int = Field(default=70, ge=0, le=100)
    budget_per_person_sgd: int = Field(default=400, ge=0)
    crowd_tolerance: Literal["low", "medium", "high"] = "medium"
    pace: str = Field(default="balanced", max_length=40)


class AgentEventRequest(BaseModel):
    event_type: str = Field(min_length=2, max_length=60)
    trip_id: str | None = None
    data: dict = Field(default_factory=dict)


class AuthRequest(BaseModel):
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(default="VibeTrip traveller", min_length=1, max_length=120)
    home_base: str = Field(default="Singapore", min_length=2, max_length=120)


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    home_base: str = Field(min_length=2, max_length=120)


app = FastAPI(title="VibeTrip Planner API", version="0.1.0")
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

AUTOCOMPLETE_MAX_PER_MINUTE = max(1, int(os.getenv("VIBETRIP_AUTOCOMPLETE_MAX_PER_MINUTE", "20")))
_autocomplete_requests: dict[str, deque[float]] = defaultdict(deque)


def _allow_autocomplete(client_key: str) -> bool:
    """Stop an accidental typing loop from exhausting the Places budget."""
    now = time.monotonic()
    requests = _autocomplete_requests[client_key]
    while requests and now - requests[0] >= 60:
        requests.popleft()
    if len(requests) >= AUTOCOMPLETE_MAX_PER_MINUTE:
        return False
    requests.append(now)
    return True


app.add_middleware(
    CORSMiddleware,
    # Vite normally runs on :5173, while the in-app preview may proxy the
    # page from another localhost port. Keep this limited to local origins.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _set_session(response: Response, user: dict) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        issue_session(user),
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite="lax",
        secure=False,
    )


@app.post("/auth/signup")
def signup(request: AuthRequest, response: Response) -> dict:
    user = auth_repository.create(request.email, request.password, request.display_name, request.home_base)
    _set_session(response, user)
    return {"user": public_user(user)}


@app.post("/auth/login")
def login(request: AuthRequest, response: Response) -> dict:
    user = auth_repository.authenticate(request.email, request.password)
    _set_session(response, user)
    return {"user": public_user(user)}


@app.post("/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/auth/me")
def authenticated_user(user: dict = Depends(get_current_user)) -> dict:
    return {"user": public_user(user)}


@app.patch("/auth/me")
def update_authenticated_user(request: ProfileUpdateRequest, user: dict = Depends(get_current_user)) -> dict:
    updated = auth_repository.update_profile(user["id"], request.display_name, request.home_base)
    if not updated:
        raise HTTPException(status_code=404, detail="User account not found.")
    return {"user": public_user(updated)}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trips/search")
async def search_route_places(request: RoutePlaceSearchRequest) -> dict:
    """Find a free-form place request near several points on the route."""
    parsed_intent = parse_place_search_intent(
        request.query,
        {
            "start": request.start,
            "destination": request.destination,
            "selected_stop": request.selected_stop_title,
            "previous_stop": request.previous_stop_title,
            "next_stop": request.next_stop_title,
            "segment_start_progress_km": request.segment_start_progress_km,
            "segment_end_progress_km": request.segment_end_progress_km,
            "target_progress_km": request.target_progress_km,
        },
    )
    provider = get_maps_provider()
    try:
        result = await provider.search_route_places(
            parsed_intent.maps_query,
            request.start,
            request.destination,
            request.budget_per_person,
            request.crowd_tolerance,
            request.route_mode,
            request.segment_start_progress_km,
            request.segment_end_progress_km,
            request.target_progress_km,
        )
    except Exception as error:
        provider = DemoMapsProvider()
        result = await provider.search_route_places(
            parsed_intent.maps_query,
            request.start,
            request.destination,
            request.budget_per_person,
            request.crowd_tolerance,
            request.route_mode,
            request.segment_start_progress_km,
            request.segment_end_progress_km,
            request.target_progress_km,
        )
        result.warning = f"Maps provider unavailable ({type(error).__name__}); showing demo matches."
    return {
        "query": request.query,
        "parsed_intent": parsed_intent.model_dump(),
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
async def plan_trip(request: TripRequest, user: dict = Depends(get_current_user)) -> dict:
    """Run the planner and return a resumable draft plan."""
    provider = get_maps_provider()
    try:
        provider_result = await provider.plan_trip(request.start, request.destination, request.budget_per_person, request.crowd_tolerance, request.start_time, request.route_mode)
    except Exception as error:
        fallback = DemoMapsProvider()
        provider = fallback
        provider_result = await fallback.plan_trip(request.start, request.destination, request.budget_per_person, request.crowd_tolerance, request.start_time, request.route_mode)
        provider_result.warning = f"Maps provider unavailable ({type(error).__name__}); showing demo candidates."
    profile = request.profile.model_dump() | {
            "preferences": request.preferences,
            "adventure_level": request.adventure_level,
            "budget_per_person_sgd": request.budget_per_person,
            "crowd_tolerance": request.crowd_tolerance,
            "pace": "adventurous" if request.adventure_level >= 70 else "laid-back" if request.adventure_level <= 35 else "balanced",
        }
    profile_context = okf_profile_exporter.export(
        profile,
        owner_id=user["id"],
        trips=trip_repository.list_saved(user["id"]),
        events=context_event_repository.list_for_owner(user["id"]),
    )
    state = request.model_dump() | {
        "route": provider_result.route,
        "candidate_places": provider_result.candidates,
        "profile_okf": profile_context["document"],
        "agent_context": profile_context["context"],
        "context_summary": profile_context["context"].get("summary", {}),
    }
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
        "recommendation_source": result.get("recommendation_source", "deterministic"),
        "recommendation_confidence": result.get("recommendation_confidence", 0),
        "recommendation_explanation": result.get("recommendation_explanation", ""),
        "profile_context": {
            "format": "okf",
            "resource": profile_context["resource"],
            "summary": profile_context["context"].get("summary", {}),
        },
        "context_summary": result.get("context_summary", profile_context["context"].get("summary", {})),
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


@app.post("/trips/save")
def save_trip(request: SaveTripRequest, user: dict = Depends(get_current_user)) -> dict:
    """Persist a complete planner draft so it can be reopened later."""
    payload = request.model_dump()
    payload["owner_id"] = user["id"]
    payload["author_name"] = f"{user['display_name']} · Exchange student"
    trip = trip_repository.save(payload)
    return {"trip": trip}


@app.post("/profiles/events")
def record_agent_event(request: AgentEventRequest, user: dict = Depends(get_current_user)) -> dict:
    """Record explicit route feedback for the user's next agent context refresh."""
    event = context_event_repository.record(
        owner_id=user["id"],
        trip_id=request.trip_id,
        event_type=request.event_type,
        data=request.data,
    )
    return {"event": event}


@app.post("/profiles/okf")
def export_okf_profile(request: UserProfileRequest, user: dict = Depends(get_current_user)) -> dict:
    """Create a private OKF context artifact for the profile/recommendation agents."""
    payload = request.model_dump()
    payload["name"] = user["display_name"]
    payload["home_base"] = user["home_base"]
    artifact = okf_profile_exporter.export(
        payload,
        owner_id=user["id"],
        trips=trip_repository.list_saved(user["id"]),
        events=context_event_repository.list_for_owner(user["id"]),
    )
    return {
        "format": artifact["format"],
        "resource": artifact["resource"],
        "document": artifact["document"],
        "summary": artifact["context"].get("summary", {}),
    }


@app.get("/trips/saved")
def saved_trips(user: dict = Depends(get_current_user)) -> dict:
    return {"trips": trip_repository.list_saved(user["id"])}


@app.delete("/trips/saved/{trip_id}")
def delete_saved_trip(trip_id: str, user: dict = Depends(get_current_user)) -> dict:
    deleted = trip_repository.delete(trip_id, user["id"])
    return {"deleted": deleted}


@app.post("/trips/saved/{trip_id}/complete")
def complete_saved_trip(trip_id: str, user: dict = Depends(get_current_user)) -> dict:
    trip = trip_repository.mark_completed(trip_id, user["id"])
    if not trip:
        raise HTTPException(status_code=404, detail="Saved trip not found")
    return {"trip": trip}


@app.patch("/trips/saved/{trip_id}/visibility")
def update_saved_trip_visibility(trip_id: str, request: VisibilityRequest, user: dict = Depends(get_current_user)) -> dict:
    trip = trip_repository.set_visibility(trip_id, user["id"], request.is_public)
    if not trip:
        raise HTTPException(status_code=404, detail="Only your saved trips can be published")
    return {"trip": trip}


@app.post("/trips/saved/{trip_id}/publish")
def publish_saved_trip(trip_id: str, request: PublishTripRequest, user: dict = Depends(get_current_user)) -> dict:
    trip = trip_repository.publish(trip_id, user["id"], request.title, request.post_caption, request.media_captions)
    if not trip:
        raise HTTPException(status_code=404, detail="Only completed saved trips can be published")
    return {"trip": trip}


@app.post("/trips/saved/{trip_id}/media")
async def upload_saved_trip_media(
    trip_id: str,
    file: UploadFile = File(...),
    caption: str = Form(default=""),
    user: dict = Depends(get_current_user),
) -> dict:
    trip = trip_repository.get(trip_id)
    if not trip or trip.get("owner_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Saved trip not found")
    if len(trip.get("media") or []) >= MAX_TRIP_MEDIA:
        raise HTTPException(status_code=409, detail=f"A trip can have up to {MAX_TRIP_MEDIA} memories.")
    media = await save_upload(trip_id, file)
    media["caption"] = caption[:240]
    updated_trip = trip_repository.add_media(trip_id, user["id"], media)
    if not updated_trip:
        raise HTTPException(status_code=404, detail="Saved trip not found")
    return {"media": media, "trip": updated_trip}


@app.put("/trips/saved/{trip_id}/media/{media_id}")
async def replace_saved_trip_media(
    trip_id: str,
    media_id: str,
    file: UploadFile = File(...),
    caption: str = Form(default=""),
    user: dict = Depends(get_current_user),
) -> dict:
    trip = trip_repository.get(trip_id)
    if not trip or trip.get("owner_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Saved trip not found")
    if not any(str(media.get("id", "")) == media_id for media in trip.get("media") or []):
        raise HTTPException(status_code=404, detail="Memory not found")
    media = await save_upload(trip_id, file)
    media["caption"] = caption[:240]
    updated_trip = trip_repository.replace_media(trip_id, user["id"], media_id, media)
    if not updated_trip:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"media": media, "trip": updated_trip}


@app.get("/trips/explore")
def explore_trips(
    preferences: str = Query(default=""),
    adventure_level: int = Query(default=70, ge=0, le=100),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    preference_list = [item.strip() for item in preferences.split(",") if item.strip()]
    return {"trips": trip_repository.list_explore(preference_list, adventure_level, limit)}


@app.get("/places/autocomplete")
async def places_autocomplete(
    request: Request,
    q: str = Query(min_length=3, max_length=100),
    session_token: str | None = Query(default=None, max_length=120),
) -> dict:
    try:
        if isinstance(get_maps_provider(), DemoMapsProvider):
            return {"suggestions": await suggest_cities(q, session_token)}
        if not _allow_autocomplete(request.client.host if request.client else "unknown"):
            raise HTTPException(status_code=429, detail="Autocomplete rate limit reached; try again shortly.")
        return {"suggestions": await suggest_cities(q, session_token)}
    except HTTPException:
        raise
    except Exception:
        return {"suggestions": []}


@app.get("/places/details")
async def places_details(
    place_id: str = Query(min_length=2, max_length=300),
    session_token: str | None = Query(default=None, max_length=120),
) -> dict:
    try:
        details = await place_details(place_id, session_token)
        return {"place": details}
    except Exception:
        return {"place": None}


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
