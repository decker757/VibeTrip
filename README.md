# VibeTrip
Codex Hackathon Project

An early MVP for an agentic road-trip planner designed around Singaporean exchange students. The current web app is a frontend prototype of the core planning loop:

1. Add a starting point and destination.
2. Set the trip context (dates, group size, budget).
3. Review an agent-produced route, detours, buffers, and timeline.
4. Adjust stops and refine the travel profile.

## Run the frontend locally

```bash
npm install
npm run dev
```

## Run the planner API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add GOOGLE_MAPS_API_KEY to .env for live Routes + Places results
uvicorn backend.main:app --reload --port 8000 --env-file .env
```

The API exposes `GET /health` and `POST /trips/plan`. The frontend calls the
planner from `src/App.jsx` and falls back to a local preview when FastAPI is
not running, so the UI remains usable without API keys.

With `GOOGLE_MAPS_API_KEY`, the backend calls the current Google Routes API to
get a driving route and samples its polyline to search nearby tourist
attractions, cafes, restaurants, and fuel stops with the Places API. Candidates
are scored inside the LangGraph detour reviewer using rating, review count,
price level, opening status, estimated crowd risk, enjoyment, and detour time.
The map UI shows the top candidates as route markers and the planner exposes
`POST /trips/simulate` to test a closure, crowd spike, or late-running event.

Google's public Places fields provide ratings, review counts, price levels, and
opening hours; they do not provide a guaranteed live crowd count. The MVP
therefore labels crowding as an estimate and lets the simulator explicitly
invalidate a stop. If you choose a free OSM stack later, use a hosted provider
or self-host Nominatim/Overpass rather than sending production traffic to the
public endpoints without following their usage and attribution policies.

## Product / agent direction

The UI is intentionally structured around four future LangGraph nodes:

- `route_scout`: calculate the fastest feasible route and surface candidate detours.
- `vibe_matcher`: infer or load an archetype from preferences, budget, group size, and energy level.
- `detour_reviewer`: score candidate places against time cost, value, weather, opening hours, and route deviation.
- `day_builder`: turn accepted places into an itinerary with driving, fuel, meal, bathroom, rest, and contingency buffers.

The eventual FastAPI boundary should expose a streaming `POST /trips/plan` endpoint so the frontend can render agent progress rather than waiting on one opaque response. Keep the planner state typed and serializable so it can be persisted as a draft and resumed if a plan changes mid-trip.
