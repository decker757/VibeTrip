# VibeTrip

<p align="center">
  <img src="./public/vibetrip-logo.png" alt="VibeTrip" width="233" />
</p>

Codex Hackathon Project

VibeTrip is a working MVP for an agentic road-trip planner designed around Singaporean exchange students. It reduces the cognitive load of planning a road trip by combining route geometry, practical breaks, personal preferences, and route-aware place recommendations:

1. Add a starting point and destination.
2. Set the trip context (dates, group size, budget).
3. Review an agent-produced route, detours, buffers, and timeline.
4. Adjust stops and refine the travel profile.
5. Save, complete, and optionally publish trips with photos or videos to Explore.

## Run the frontend locally

```bash
npm install
npm run dev
```

## Run the planner API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add GOOGLE_MAPS_API_KEY for live Routes + Places results.
# Add VITE_GOOGLE_MAPS_BROWSER_KEY for the interactive browser map.
# Optional: start Postgres with `docker compose up -d postgres`.
# DATABASE_URL is already provided in `.env.example` for that container.
uvicorn backend.main:app --reload --port 8000 --env-file .env
```

Open a second terminal for the frontend:

```bash
npm install
npm run dev
```

Docker is optional. It is only needed for the local Postgres service; the app
falls back to memory/localStorage when Postgres is not running.

The API exposes `GET /health`, `POST /trips/plan`, `POST /trips/reroute`, and
`POST /trips/search`, `POST /trips/save`, `GET /trips/saved`,
`DELETE /trips/saved/{id}`, `POST /trips/saved/{id}/complete`,
`PATCH /trips/saved/{id}/visibility`, `POST /trips/saved/{id}/media`, and
`GET /trips/explore`, plus `POST /profiles/okf` for a private agent context
artifact. Authentication is provided by `POST /auth/signup`, `POST /auth/login`,
`POST /auth/logout`, `GET /auth/me`, and `PATCH /auth/me`.
The frontend calls the planner from `src/App.jsx` and falls back to a local
preview when FastAPI is not running, so the UI remains usable without API keys.
The browser routes are `/login`, `/onboarding`, `/plan`, `/explore`,
`/saved-trips`, and `/profile`. Unauthenticated visitors are sent to `/login`;
the first successful sign-in for an account opens `/onboarding` so they can set
their travel preferences before entering the planner. Completing onboarding is
stored per account in the browser, and the preferences can be changed later
from the account menu’s Travel profile page.

### Demo mode versus live mode

The repository is designed to remain judgeable without paid provider keys:

- **Demo mode:** omit Google and OpenAI keys. The deterministic provider returns
  seeded route/place data and the UI remains fully navigable.
- **Live map mode:** provide both `GOOGLE_MAPS_API_KEY` for the backend Routes +
  Places calls and `VITE_GOOGLE_MAPS_BROWSER_KEY` for the browser map. Restrict
  the browser key by HTTP referrer and restrict the server key by API and quota.
- **LLM review:** provide `OPENAI_API_KEY` and keep `VIBETRIP_LLM_ENABLED=true`.
  The LLM is optional and only ranks deterministic, already-validated
  candidates.

Never put `GOOGLE_MAPS_API_KEY` or `OPENAI_API_KEY` in a `VITE_*` variable or
commit them to Git. Google Maps usage requires billing, so set quota and budget
alerts before enabling live mode.

### Environment variables

Copy `.env.example` to `.env` and configure only what the chosen mode needs:

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_MAPS_API_KEY` | Live mode | Backend Routes and Places requests |
| `VITE_GOOGLE_MAPS_BROWSER_KEY` | Live mode | Interactive browser map |
| `OPENAI_API_KEY` | Optional | LLM recommendation reviewer |
| `VITE_API_URL` | Deployment | Public backend URL used by the frontend |
| `VIBETRIP_AUTH_SECRET` | Deployment | Secret used to sign session cookies |
| `DATABASE_URL` | Persistent data | Postgres connection string |
| `VIBETRIP_MEDIA_DIR` | Optional | Local media storage directory |
| `VIBETRIP_OKF_DIR` | Optional | Local OKF profile directory |

`VITE_*` values are bundled into the browser and are not secret. The server
variables must remain backend-only.

## Verification checklist

Run these checks before opening a pull request or recording the demo:

```bash
npm run build
python3 -m compileall -q backend
git diff --check
```

Then manually verify the primary journey:

1. Create an account or use the demo login.
2. Complete onboarding and confirm the name and travel profile are reflected in
   the planner.
3. Generate a route with dates, start time, travellers, budget, and route style.
4. Replace one stop through the route assistant and confirm the route is
   recalculated through the replacement waypoint in the correct order.
5. Add an optional destination stop and verify the timeline and route update.
6. Save the trip, mark it complete, add media, publish it, and find it through
   Explore search, filters, and pagination.
7. Test logout/login, a second account, keyboard focus, mobile layout, and the
   no-API-key demo fallback.

The current repository has no automated test suite yet, so the manual journey
above is an important pre-submission check.

## Saved trips and Explore

Saved drafts use a small repository boundary in `backend/storage.py`. When
`DATABASE_URL` points to the local Compose service and `psycopg` is installed,
the repository stores complete trip drafts in Postgres JSONB columns. If the
database is not running, the API falls back to process memory and the browser
also keeps local-preview saves in `localStorage`. Start the database with:

```bash
docker compose up -d postgres
```

The MVP uses the authenticated user ID as the owner. The user profile is
intentionally lightweight: display name and home base are stored with the local
account, while “exchange student” is the only planning context needed.
Saved trips are private drafts by default. A user can mark a draft completed,
attach memories, and publish it; Explore only includes trips that are both
`is_public` and `is_completed`. The feed ranks public routes using preference
overlap and adventure-level distance. Explore also has a local search bar for
published trip ideas and route-style filters; this does not call Google Places.
Live place discovery stays inside the planner’s route assistant, where a search
can be constrained to the selected route segment before making a provider call.

### Memories and media

Completed trips can accept JPG, PNG, WebP, GIF, MP4, WebM, and MOV uploads up to
20 MB through `POST /trips/saved/{id}/media`. The local MVP stores files under
`backend/media/` and returns stable `/media/...` URLs. Set `VIBETRIP_MEDIA_DIR`
to use another local directory. This adapter is deliberately isolated so it
can be replaced with S3, Cloudflare R2, or another sharable object store later
without changing the trip or Explore response shape. Media is never required:
routes without memories use a generated route cover in the UI.

### Local authentication

The judging build uses a self-contained local auth adapter, so no Supabase or
other hosted identity project is required. User records are stored in the
private, Git-ignored `backend/auth_users.json`; passwords are scrypt-hashed and
the API sets a signed HttpOnly session cookie. The first API startup seeds the
demo account:

```text
Email: demo@vibetrip.local
Password: vibetrip-demo
```

New accounts receive unique IDs, and those IDs namespace saved trips and OKF
profile documents. Set `VIBETRIP_AUTH_SECRET` in `.env` outside demo mode. This
adapter is intentionally replaceable with managed authentication before
production deployment.

### OKF agent context

`POST /profiles/okf` exports the current structured travel profile as a private
OKF v0.1-style Markdown document. The planner also refreshes this artifact
automatically before each route generation and passes it to the optional LLM
reviewer. The OKF document is context, not authority: route geometry, opening
hours, waypoint ordering, and budget checks remain deterministic. Local files
are written to `backend/okf_profiles/` and ignored by Git; set
`VIBETRIP_OKF_DIR` to use another private directory or replace the adapter with
an object-store/knowledge-catalog writer later.

With `GOOGLE_MAPS_API_KEY`, the backend calls the current Google Routes API to
get a driving route and samples its polyline to search nearby tourist
attractions, cafes, restaurants, and fuel stops with the Places API. Candidates
are scored inside the LangGraph detour reviewer using rating, review count,
price level, opening status, estimated crowd risk, enjoyment, and detour time.
The map UI shows the top candidates as route markers and the planner exposes
`POST /trips/simulate` to test a closure, crowd spike, or late-running event.

`POST /trips/search` powers the route-request assistant. It accepts a
natural-language request such as “a quiet cafe with a view” and, when replacing
an existing timeline stop, searches only the geographic segment between the
previous and next checkpoints. Results are ordered by route progress near the
selected stop before enjoyment scoring is used as a tie-break. The MVP does not need a vector store for
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

The current FastAPI boundary exposes a synchronous `POST /trips/plan` endpoint
and keeps planner state typed and serializable so drafts can be saved and
resumed. Streaming agent progress remains a future enhancement.

## Deploying the MVP

For a hosted demo, deploy the Vite frontend and FastAPI backend separately. Set
`VITE_API_URL` to the public backend URL before building the frontend, and set
the backend's `VIBETRIP_AUTH_SECRET` to a long random value. A hosted Postgres
instance is recommended for saved trips; the default local JSON, memory, and
filesystem adapters are intended for judging and local development, not
durable production storage.

Uploaded memories also need persistent object storage or a persistent volume in
deployment. The current media adapter writes to `backend/media/`, so ephemeral
hosting will lose uploads after a restart. Replace it with S3, Cloudflare R2,
or another sharable object store before treating the app as production-ready.

Before publishing a repository or demo, confirm that `.env`, API keys, local
auth data, OKF artifacts, media, and database volumes are not committed. The
repository's `.gitignore` excludes these local state files.

## Remaining roadmap

The MVP is implemented and ready for end-to-end validation. The remaining
items below are hardening work rather than prerequisites for the local demo.

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

### Phase 2 — Planner reliability and live-trip readiness (remaining)

- Add end-to-end tests for waypoint ordering, opening hours, budget limits,
  realistic first-stop timing, rerouting, and simulator recalibration.
- Add streaming planner progress so the UI can show the agents working.
- Improve live traffic, construction, crowd-estimate, and provider-error
  handling while clearly labelling estimates.
- Finish accessibility and mobile checks, including readable type, keyboard
  controls, focus states, and large touch targets.

### Phase 3 — Saved trips and social foundation (implemented for MVP)

- Saved drafts are stored through the repository boundary, using Postgres JSONB
  when available and local browser/API fallbacks when it is not.
- Users can mark a trip completed, attach photos or videos, keep it private, or
  publish it to the Explore feed.
- The local media adapter validates MIME type and a 20 MB size limit. Replace it
  with signed uploads and thumbnails when deploying object storage. Each trip can
  store up to five memories, and Explore opens a post detail view showing those
  memories and the ordered stops before the user remixes the route. Built-in
  Explore seed routes include two demo memory images separate from their route
  covers; real users can add memories up to the five-item limit.
- Explore is a preference-ranked, media-first community feed seeded with public
  exchange-student routes. Reporting, moderation, comments, follows, and real
  authentication remain post-MVP work.

### Phase 4 — Product expansion and deployment

- Add route sharing and richer Google Maps handoff for the final ordered stop
  list.
- Add saved places, trip-history retrieval, and only then evaluate a vector
  store for persistent taste and semantic discovery.
- Move local authentication to a managed identity provider, add secret
  management, logging, usage limits, cost tracking, and a deployed
  Postgres/object-storage environment.

The implemented MVP order is: frontend modularization → optional LLM shortlist
decision → route-aware saved drafts → local authentication and per-user OKF
context → completion and media memories → preference-ranked Explore feed. The
next production order is: managed authentication and hosted ownership → signed
object storage/thumbnails → moderation and reporting → streaming planner
progress → richer social interactions. This keeps the route experience
maintainable and trustworthy before adding engagement mechanics.
