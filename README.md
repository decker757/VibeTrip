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
# Add GOOGLE_MAPS_API_KEY for live Routes + Places results.
# Add VITE_GOOGLE_MAPS_BROWSER_KEY for the interactive browser map.
# Optional: start Postgres with `docker compose up -d postgres`.
# DATABASE_URL is already provided in `.env.example` for that container.
uvicorn backend.main:app --reload --port 8000 --env-file .env
```

The API exposes `GET /health`, `POST /trips/plan`, `POST /trips/reroute`, and
`POST /trips/search`, `POST /trips/save`, `GET /trips/saved`,
`DELETE /trips/saved/{id}`, and `GET /trips/explore`.
The frontend calls the planner from `src/App.jsx` and falls back to a local
preview when FastAPI is not running, so the UI remains usable without API keys.

## Saved trips and Explore

Saved drafts use a small repository boundary in `backend/storage.py`. When
`DATABASE_URL` points to the local Compose service and `psycopg` is installed,
the repository stores complete trip drafts in Postgres JSONB columns. If the
database is not running, the API falls back to process memory and the browser
also keeps local-preview saves in `localStorage`. Start the database with:

```bash
docker compose up -d postgres
```

The MVP uses `demo-user` as the owner until authentication is added. Saved
trips are private by default. Explore is seeded with public exchange-student
routes and ranks them using preference overlap and adventure-level distance;
only trips marked `is_public` are eligible for that feed.

With `GOOGLE_MAPS_API_KEY`, the backend calls the current Google Routes API to
get a driving route and samples its polyline to search nearby tourist
attractions, cafes, restaurants, and fuel stops with the Places API. Candidates
are scored inside the LangGraph detour reviewer using rating, review count,
price level, opening status, estimated crowd risk, enjoyment, and detour time.
The map UI shows the top candidates as route markers and the planner exposes
`POST /trips/simulate` to test a closure, crowd spike, or late-running event.

`POST /trips/search` powers the route-request assistant. It accepts a
natural-language request such as “a quiet cafe with a view” and searches
several points along the current route before returning scored alternatives
that can be used as a draft stop. The MVP does not need a vector store for
this live discovery flow: Google Places handles free-form place search, while
LangGraph remains responsible for route fit and itinerary decisions. A vector
store becomes useful later for persistent user taste, saved places, and
trip-history retrieval.

`POST /trips/reroute` is used after a user adds, removes, or replaces a stop.
It sends the edited places as ordered route waypoints so the map geometry is
recomputed through the actual stops instead of leaving them as nearby markers.

Google's public Places fields provide ratings, review counts, price levels, and
opening hours; they do not provide a guaranteed live crowd count. The MVP
therefore labels crowding as an estimate and lets the simulator explicitly
invalidate a stop. If you choose a free OSM stack later, use a hosted provider
or self-host Nominatim/Overpass rather than sending production traffic to the
public endpoints without following their usage and attribution policies.

## Product / agent direction

The UI is intentionally structured around five LangGraph nodes:

- `route_scout`: calculate the fastest feasible route and surface candidate detours.
- `vibe_matcher`: infer or load an archetype from preferences, budget, group size, and energy level.
- `detour_reviewer`: score candidate places against time cost, value, weather, opening hours, and route deviation.
- `day_builder`: turn accepted places into an itinerary with real fuel or convenience stops, meals, scenic detours, and contingency buffers.
- `route_requester`: translate natural-language feedback into a route-aware Places search and return replacement candidates.

Route style and travel profile are intentionally separate inputs. `fastest`,
`balanced`, and `scenic` control route geometry and how many detours the day
builder may add. The adventure slider only changes recommendation scoring and
the inferred archetype within that route strategy.

The eventual FastAPI boundary should expose a streaming `POST /trips/plan` endpoint so the frontend can render agent progress rather than waiting on one opaque response. Keep the planner state typed and serializable so it can be persisted as a draft and resumed if a plan changes mid-trip.
