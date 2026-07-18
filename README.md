# VibeTrip

<p align="center">
  <img src="./public/vibetrip-logo.png" alt="VibeTrip" width="233" />
</p>

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

The planner is a small, typed LangGraph workflow supported by route, Places,
simulation, and persistence services. The current graph has five nodes; the
route-request assistant is a separate route-aware search capability. The fifth
node is optional: it calls an LLM only when configured and otherwise preserves
the deterministic recommendation result.

### What each planner agent does

1. **Route scout (`route_scout`)**
   - Establishes the baseline driving route between the origin and destination.
   - Supplies distance, drive time, traffic-aware estimates, route geometry, and
     the corridor used to discover nearby places.
   - Keeps destination-area recommendations separate from places that are
     genuinely along the route.

2. **Vibe matcher (`vibe_matcher`)**
   - Converts the travel profile into a lightweight archetype such as
     “Curious, not rushed” or “Easygoing explorer.”
   - Combines explicit preferences, adventure-slider level, group size, and
     student-budget context.
   - Sets planning defaults such as the buffer allowance and recommendation
     balance; it does not change the road geometry.

3. **Detour reviewer (`detour_reviewer`)**
   - Scores candidate attractions, eateries, cafes, fuel stations, and
     convenience stores.
   - Weighs rating quality, review volume, price, estimated crowd risk,
     enjoyment, opening hours, detour time, route style, and adventure level.
   - Selects the best along-route candidates for the current route mode:
     `fastest` keeps only essentials, `balanced` allows worthwhile detours,
     and `scenic` allows more intermediate experiences.

4. **LLM recommendation reviewer (`llm_reviewer`)**
   - Receives only a shortlist that has already passed deterministic route and
     availability checks.
   - Interprets the user's structured profile and route context, ranks
     subjective fit, and returns candidate IDs plus a short rationale using
     structured output.
   - Cannot invent places, coordinates, prices, reviews, opening hours, or
     route geometry. If the key is missing or the call fails, the graph keeps
     the deterministic reviewer result.

5. **Day builder (`day_builder`)**
   - Converts selected places into an ordered, time-aware itinerary.
   - Adds practical fuel, bathroom, snack, and convenience stops where the
     drive length warrants them; it does not invent “stop anywhere” breaks.
   - Uses route progress as the ordering key, checks regular opening hours at
     the estimated arrival time, and reserves driving, stop, and contingency
     buffers before check-in.

### Supporting route agents and services

- **Route-request assistant (`POST /trips/search`)** translates a natural-
  language request such as “quiet Chinese food under my budget” into a focused
  Places search along the current route. It returns replacement candidates for
  the selected timeline stop; it does not replace every stop at once.
- **Reroute service (`POST /trips/reroute`)** turns a user’s add, change, or
  remove action into ordered waypoint coordinates and asks the route provider
  to recompute the geometry through those actual places.
- **Trip simulator (`POST /trips/simulate`)** applies a closure, crowd spike,
  or late-running event to one current stop, then chooses a feasible backup or
  sends the group directly onward.
- **Destination explorer** keeps post-arrival ideas optional until the user
  selects “Add to route.” That action promotes the place into the active
  itinerary before check-in and triggers the same reroute service.

The end-to-end graph is:

```text
route_scout → vibe_matcher → detour_reviewer → llm_reviewer → day_builder
                                                   ↓
                                      ordered itinerary + route constraints
```

Route style and travel profile are intentionally separate inputs. `fastest`,
`balanced`, and `scenic` control route geometry and how many detours the day
builder may add. The adventure slider only changes recommendation scoring and
the inferred archetype within that route strategy.

The eventual FastAPI boundary should expose a streaming `POST /trips/plan` endpoint so the frontend can render agent progress rather than waiting on one opaque response. Keep the planner state typed and serializable so it can be persisted as a draft and resumed if a plan changes mid-trip.

## Remaining roadmap

The next implementation step is to harden the new modular boundary and LLM
fallback behavior without giving the model control of routing or safety-critical
constraints.

### Phase 0 — Frontend modularization (implemented)

- Break `src/App.jsx` into focused page sections and components for planning,
  route display, itinerary management, destination suggestions, travel profile,
  chatbot search, simulator, saved trips, and Explore.
- Extract rendering, formatting, map previews, itinerary controls, and
  collection views into focused modules. API and state hooks remain the next
  cleanup target as the planner grows.
- Keep shared types, formatting helpers, and itinerary actions in reusable
  modules so edits, reroutes, simulations, and saved trips use one source of
  truth.
- Preserve the current behavior while adding component-level tests before the
  LLM and social features increase the surface area further.

### Phase 1 — LLM-assisted recommendations (implemented, optional)

- The `llm_reviewer` node runs after deterministic Places filtering.
- Give it a small shortlist of feasible candidates plus the user's profile,
  route mode, budget, arrival window, and route preferences.
- Let it rank subjective fit, explain the trade-offs, and choose among the
  feasible candidates already found by the Places layer.
- Validate its structured response against hard constraints, then pass the
  accepted choice to the existing deterministic reroute and day-builder flow.
- Keeps a deterministic fallback for missing API keys, timeouts, invalid output,
  and rate limits. The model must not invent places, prices, reviews, hours,
  coordinates, or route geometry.

### Phase 2 — Planner reliability and live-trip readiness

- Add end-to-end tests for waypoint ordering, opening hours, budget limits,
  realistic first-stop timing, rerouting, and simulator recalibration.
- Add streaming planner progress so the UI can show the agents working.
- Improve live traffic, construction, crowd-estimate, and provider-error
  handling while clearly labelling estimates.
- Finish accessibility and mobile checks, including readable type, keyboard
  controls, focus states, and large touch targets.

### Phase 3 — Saved trips and social foundation

- Move from demo ownership to users, authentication, privacy controls, and
  durable Postgres-backed trip records.
- Add trip completion so users can mark stops visited and attach notes, photos,
  and videos.
- Add sharable object storage using signed upload URLs, media validation, size
  limits, thumbnails, and deletion support.
- Build the Explore feed around public completed trips, with media-first cards,
  preference-aware ranking, and reporting/moderation controls.

### Phase 4 — Product expansion and deployment

- Add route sharing and richer Google Maps/Waze handoff for the final ordered
  stop list.
- Add saved places, trip-history retrieval, and only then evaluate a vector
  store for persistent taste and semantic discovery.
- Add authentication, secret management, logging, usage limits, cost tracking,
  and a deployed Postgres/object-storage environment.

The recommended order is: frontend modularization → LLM shortlist decision →
reliability tests and streaming → authenticated saved trips and media → Explore
social feed. This keeps the core route experience maintainable and trustworthy
before adding the larger social surface.
