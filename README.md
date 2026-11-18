<p align="center">
  <img src="https://cdn.jsdelivr.net/gh/decker757/VibeTrip@main/public/vibetrip-readme-logo.png" alt="VibeTrip" width="487" />
</p>

## Codex Hackathon Project

VibeTrip is a working MVP for an agentic road-trip planner designed around Singaporean exchange students. It reduces the cognitive load of planning a road trip by combining route geometry, practical breaks, personal preferences, and route-aware place recommendations:

1. Add a starting point and destination.
2. Set the trip context (dates, group size, budget).
3. Review an agent-produced route, detours, buffers, and timeline.
4. Adjust stops and refine the travel profile.
5. Save, complete, and optionally publish trips with photos or videos to Explore.

## How Codex accelerated development

VibeTrip was developed iteratively in Codex, using GPT-5.6 as the coding and
reasoning model for product, design, and engineering decisions. Codex turned
user research observations, screenshots, and bug reports into working changes
across the React frontend, FastAPI backend, LangGraph workflow, persistence
layer, and README. The app's optional runtime LLM configuration is separate
from this development workflow and can be disabled for deterministic demo
mode.

The collaboration loop was conversational: I supplied product intent,
screenshots, and observed failures; Codex traced them to the relevant code,
proposed implementation choices, applied the changes, and helped verify the
result against the running app and regression checks.

### Skills and workflow used

- **UI/UX Pro Max:** used to review screenshots and improve information
  hierarchy, responsive layout, accessibility, focus states, form feedback,
  loading states, map interactions, timeline affordances, saved-trip actions,
  media previews, and Explore navigation.
- **Bug Journal:** maintained a persistent record of non-trivial failures with
  their symptom, root cause, fix, and one prevention rule. This made recurring
  issues—such as route waypoint ordering, checkpoint-preserving Explore reuse,
  missing Fastest fuel stops, map marker interactions, and billable API
  request limits—available as regression guidance during later changes.
- **Graphify:** indexed the repository as a local, queryable knowledge graph
  so Codex could trace relationships across the frontend, FastAPI backend,
  route graph, providers, storage adapters, and SQL schema before opening the
  smallest relevant set of files.

For the repository-navigation workflow, install Graphify once, register its
Codex skill, and build or refresh the local index:

```bash
pip install "graphifyy[sql]"
graphify install --platform codex
```

```text
/graphify .
/graphify . --update
```

The generated `graphify-out/` directory is a local index containing the graph,
interactive visualization, and architecture report; it is ignored by Git.

### Key product and engineering decisions

- Route geometry, waypoint order, opening hours, budget, and safety constraints
  remain deterministic.
- The optional LLM adds subjective ranking and explanation only after hard
  feasibility filtering; it cannot invent places or route data.
- Agency is bounded to two places where judgement helps and output can be
  checked: the route request agent and the late-arrival repair loop.
- OKF is a derived agent-readable context artifact, not a replacement for the
  database.
- A vector store is deferred until saved-place discovery or semantic
  trip-history retrieval actually requires one.
- Google Maps, Places, and OpenAI remain optional so the project is still
  demonstrable in deterministic demo mode, while live capabilities can be
  enabled independently.

## Architecture overview

The high-level flow keeps the browser focused on interaction, the FastAPI
boundary responsible for validation and orchestration, and deterministic route
checks authoritative over optional provider and LLM suggestions.

```mermaid
flowchart LR
    UI["React + Vite frontend<br/>Planner · Explore · Saved Trips · Profile"]
    API["FastAPI API"]
    GRAPH["LangGraph planner<br/>route scout → vibe matcher → detour reviewer → optional LLM reviewer → day builder ⇄ repair loop"]
    AGENT["Route request agent<br/>LLM ⇄ search / hours / budget tools"]
    SEARCH["Route-aware search<br/>reroute · simulator"]
    PROVIDERS["Provider boundary"]
    MAPS["Google Routes + Places<br/>optional live mode"]
    LLM["OpenAI reviewer<br/>optional"]
    AUTH["Local authentication"]
    STORE["Storage adapters<br/>memory · JSON · optional Postgres"]
    OKF["OKF context + feedback events"]
    EXPLORE["Saved trips · Explore · media"]
    BROWSER["Google Maps JavaScript<br/>optional browser key"]

    UI -->|REST + auth| API
    UI -->|interactive map| BROWSER
    API --> GRAPH
    API --> SEARCH
    SEARCH --> AGENT
    AGENT -. bounded tool calls .-> LLM
    API --> AUTH
    API --> STORE
    API --> EXPLORE
    GRAPH --> PROVIDERS
    SEARCH --> PROVIDERS
    PROVIDERS --> MAPS
    GRAPH -. validated shortlist .-> LLM
    STORE --> OKF
    OKF --> GRAPH
```

## Run the frontend locally

```bash
npm install
npm run dev
```

## Run the planner API

For judging, copy the template and paste the provided demo keys into `.env`.
Keep this file local; it is ignored by Git.

```dotenv
GOOGLE_MAPS_API_KEY=<provided-google-server-key>
VIBETRIP_LIVE_MAPS_ENABLED=true

VITE_GOOGLE_MAPS_BROWSER_ENABLED=true
VITE_GOOGLE_MAPS_BROWSER_KEY=<provided-google-browser-key>
VITE_GOOGLE_MAPS_MAP_ID=<provided-google-map-id-or-DEMO_MAP_ID>

OPENAI_API_KEY=<provided-openai-key>
VIBETRIP_LLM_ENABLED=true
VIBETRIP_LLM_SEARCH_ENABLED=true
VIBETRIP_LLM_MODEL=gpt-4o-mini

VITE_API_URL=http://localhost:8000
VIBETRIP_AUTH_SECRET=vibetrip-local-development-secret
```

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with the provided keys above.
uvicorn backend.main:app --reload --port 8000 --env-file .env
```

Open a second terminal for the frontend:

```bash
npm install
npm run dev
```

Docker is optional and not required for the judged local MVP flow. The app uses
local auth, process memory, and browser `localStorage` fallbacks when no
database is running.

The API exposes `GET /health`, `POST /trips/plan`, `POST /trips/reroute`, and
`POST /trips/search`, `POST /trips/save`, `GET /trips/saved`,
`DELETE /trips/saved/{id}`, `POST /trips/saved/{id}/complete`,
`PATCH /trips/saved/{id}/visibility`, `POST /trips/saved/{id}/media`, and
`GET /trips/explore`, plus `POST /profiles/okf` for a private agent context
artifact and `POST /profiles/events` for explicit route feedback. Authentication is provided by `POST /auth/signup`, `POST /auth/login`,
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
- **Live map mode:** explicitly set `VIBETRIP_LIVE_MAPS_ENABLED=true`, provide
  `GOOGLE_MAPS_API_KEY` for the backend Routes + Places calls, and provide
  `VITE_GOOGLE_MAPS_BROWSER_ENABLED=true` plus
  `VITE_GOOGLE_MAPS_BROWSER_KEY` for the browser map. Restrict the browser key
  by HTTP referrer and restrict the server key by API and quota.
- **LLM review and route requests:** provide `OPENAI_API_KEY` and keep
  `VIBETRIP_LLM_ENABLED=true`. `VIBETRIP_LLM_SEARCH_ENABLED=true` lets the
  route assistant parse conversational requests into a concise Maps query,
  while the backend still enforces explicit locality, checkpoint ordering,
  opening hours, and budget constraints deterministically. The LLM may rank
  or interpret requests, but it cannot invent places or override geography.
- **Cost guard:** live autocomplete waits for three characters, debounces
  requests, uses one Places session token per field interaction, and applies a
  per-client rolling-minute limit controlled by
  `VIBETRIP_AUTOCOMPLETE_MAX_PER_MINUTE` (default `20`). Broad place searches
  request ranking/scheduling fields only; review text is intentionally deferred.
  Nearby categories are batched into one search per sampled route point instead
  of one request per category.
  The backend also applies process-local circuit breakers to Routes, Places
  search, and Place Details (defaults `10`, `30`, and `20` requests per minute)
  and falls back to demo data when a limit is reached. Lower these values for a
  live demo, and still configure Google Cloud quotas because these guards reset
  when the backend process restarts.
- **Hard off switch:** set `VIBETRIP_LIVE_MAPS_ENABLED=false` to force the
  deterministic demo provider even if a Google key remains in `.env`.

### Demo account and fallback mode

No separate seed script is required for judging. On first API startup, the
local auth adapter creates the demo account shown below. If Google Maps keys
are provided, the planner uses live Routes and Places results. If keys are
omitted, the deterministic provider supplies fallback route geometry, route
candidates, fuel stops, destination suggestions, and Explore examples so the
planner can still be exercised end to end. Saved drafts fall back to process
memory and browser `localStorage` in the judged local flow.

Never put `GOOGLE_MAPS_API_KEY` or `OPENAI_API_KEY` in a `VITE_*` variable or
commit them to Git. Google Maps usage requires billing, so set quota and budget
alerts before enabling live mode.

### Environment variables

Copy `.env.example` to `.env` and configure only what the chosen mode needs:

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_MAPS_API_KEY` | Live mode | Backend Routes and Places requests |
| `VIBETRIP_LIVE_MAPS_ENABLED` | Live mode | Explicitly enables billable backend Maps calls |
| `VITE_GOOGLE_MAPS_BROWSER_KEY` | Live mode | Interactive browser map |
| `VITE_GOOGLE_MAPS_BROWSER_ENABLED` | Live mode | Explicitly enables billable browser map loads |
| `OPENAI_API_KEY` | Optional | LLM recommendation reviewer |
| `VIBETRIP_LLM_SEARCH_ENABLED` | Optional | LLM parser for route assistant requests; also gates the route agent |
| `VIBETRIP_LLM_SEARCH_MAX_PER_MINUTE` | Optional | Process-local route assistant LLM limit |
| `VIBETRIP_ROUTE_AGENT_ENABLED` | Optional | Set `false` to use the single-call search instead of the route agent |
| `VIBETRIP_AGENT_TIMEOUT_SECONDS` | Optional | Wall-clock limit for one route agent run (default `20`) |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` | Optional | LangSmith tracing; off by default and sends prompts to LangSmith |
| `VITE_API_URL` | Deployment | Public backend URL used by the frontend |
| `VIBETRIP_AUTH_SECRET` | Deployment | Secret used to sign session cookies |
| `DATABASE_URL` | Optional | Postgres adapter connection string |
| `VIBETRIP_MEDIA_DIR` | Optional | Local media storage directory |
| `VIBETRIP_OKF_DIR` | Optional | Local OKF profile directory |
| `VIBETRIP_AUTOCOMPLETE_MAX_PER_MINUTE` | Live mode | Per-client autocomplete safety limit |
| `VIBETRIP_GOOGLE_ROUTES_MAX_PER_MINUTE` | Live mode | Process-local Routes circuit breaker |
| `VIBETRIP_GOOGLE_PLACES_MAX_PER_MINUTE` | Live mode | Process-local Places search circuit breaker |
| `VIBETRIP_GOOGLE_DETAILS_MAX_PER_MINUTE` | Live mode | Process-local Place Details circuit breaker |

`VITE_*` values are bundled into the browser and are not secret. The server
variables must remain backend-only.

## Verification checklist

Run these checks before opening a pull request or recording the demo:

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
npm run build
python3 -m compileall -q backend
git diff --check
```

The pytest suite runs offline: it clears the Google and OpenAI keys, uses the
demo provider, and scripts LLM responses with fake chat models.

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

Automated tests cover the planner, repair loop, route agent, storage, and
profile context; the manual journey above still checks the UI end to end.

## Saved trips and Explore

Saved drafts use a small repository boundary in `backend/storage.py`. For the
judged local MVP, the API can fall back to process memory and the browser also
keeps local-preview saves in `localStorage`, so Postgres is not required to run
or demonstrate the core flow. When `DATABASE_URL` is set and Postgres is
reachable, saved trips are also written there and read back; if it is
unavailable the API falls back to memory. The local Compose service can be
started with:

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

`POST /profiles/okf` exports a private, versioned OKF-style Markdown context
document for the authenticated traveller. It combines the current profile,
the user's saved trip history, and explicit route feedback stored in the
`trip_events` table. The planner refreshes this artifact automatically before
each route generation, passes the structured context through LangGraph, and
includes it in the optional LLM reviewer prompt. The document is context, not
authority: route geometry, opening hours, waypoint ordering, and budget checks
remain deterministic. Local files are written to `backend/okf_profiles/` and
ignored by Git; set `VIBETRIP_OKF_DIR` to use another private directory or
replace the adapter with an object-store/knowledge-catalog writer later.

The frontend records meaningful feedback such as replacing a stop, removing a
stop, using an Explore route, and searching for a better fit through
`POST /profiles/events`. On the next generation, the context builder turns
those events into soft signals such as local food, quieter stops, scenic views,
or budget-conscious choices. This is the value of OKF plus the database: the
agent receives a compact, human-readable preference memory derived from real
trip behaviour without adding a vector store to the MVP.

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

VibeTrip is a **LangGraph workflow with two bounded agentic parts**. The split
is deliberate: deterministic code owns every fact the trip depends on (route
geometry, waypoint order, opening hours, budget, safety), and an LLM is used
only where judgement helps and its output can be checked.

| Part | Who decides what happens next | Where |
|---|---|---|
| Planner pipeline (route → profile → ranking → schedule) | Code | `backend/graph.py` |
| Recommendation reviewer (optional) | LLM ranks a pre-validated shortlist; code keeps only known ids | `backend/recommender.py` |
| **Repair loop** | **LLM chooses which optional stop to give up when a trip runs late** | `backend/repair.py` |
| **Route request agent** | **LLM chooses which tool to call, reads the result, and decides whether to keep searching** | `backend/route_agent.py` |

Every LLM path has a deterministic fallback, so the app runs end to end with no
OpenAI key.

### Planner graph

```text
route_scout → vibe_matcher → detour_reviewer → llm_reviewer → day_builder
                                                                   │
                                        late arrival & fixable? ───┤
                                                  yes ↓            │ no
                                               repair ─→ day_builder   → finalize
```

- **`route_scout`** calls the maps provider (Google Routes + Places, or the
  demo provider) and falls back to demo data if the provider fails.
- **`vibe_matcher`** turns the profile, adventure level, and learned signals
  into an archetype; it never changes geometry.
- **`detour_reviewer`** scores candidates (rating, reviews, price, crowd risk,
  detour time, route mode, learned preferences) and drops closed places.
- **`llm_reviewer`** (optional) lets the LLM rank at most 10 feasible
  candidates with structured output; unknown ids are dropped.
- **`day_builder`** orders stops by route progress, checks opening hours at the
  estimated arrival, adds a 20% driving buffer, handles multi-day trips, and
  returns structured `route.warnings`.
- **`repair`** runs only when the trip arrives after the target end time and
  skipping optional stops could fix it. The LLM picks one of
  `skip_coffee`, `skip_attraction`, `skip_extra_fuel`, `accept_warning`, using
  the traveller's profile (an adventurous traveller keeps the lookout and drops
  coffee). Code applies the skip and rebuilds. At most 2 attempts; the meal and
  the only fuel stop are never skipped; the route mode is never changed; the
  best attempt (fewest warnings, then earliest arrival) is kept. Without an LLM
  a rule picks coffee → extra fuel → attraction. If the trip would still be
  late with every optional stop skipped, nothing is stripped and the warning
  suggests starting earlier, allowing a later end time, or trying Fastest. The same repair step runs again after the stops are added
  as real waypoints, so `repair_log` matches the warning the user sees.

### Route request agent (`POST /trips/search`)

The user picks a timeline stop and describes what they want ("a quiet cafe with
a view"). When an LLM is configured, a small hand-written LangGraph agent
(`agent` node ↔ `tools` node, with a conditional "continue?" edge) handles it:

| Tool | The LLM supplies | Code enforces |
|---|---|---|
| `SearchPlaces` | free-text query + category | segment between the neighbouring stops, budget, crowd tolerance, route mode; route geometry fetched once per run |
| `CheckOpenAtArrival` | place ids | opening hours at the stop's arrival time |
| `CheckBudget` | place ids | cost vs the stop being replaced and the remaining budget |
| `SubmitShortlist` | ids + one-sentence rationale | ids must come from a search; closed places are dropped even if the agent never checked |

Caps: 3 searches and 8 steps per run, a wall-clock timeout
(`VIBETRIP_AGENT_TIMEOUT_SECONDS`, default 20), and one slot of the LLM search
per-minute limiter. On any failure, timeout, or empty validated shortlist the
endpoint returns today's deterministic search instead. The response adds
`agent_source`, `agent_rationale`, and `agent_trace`; the assistant card shows
the rationale and a collapsible "How the agent got here" list. Results carry
`agent_pick`: the agent's shortlist comes first, and other places it saw on the
same leg follow under an "Also found along this leg" label, so extras are not
presented as the agent's choices.

### Make room for the destination (`POST /trips/plan` with `destination_activity`)

Travellers rarely know when they want to arrive, but they do know what they
want to do once they get there. So the deadline comes from the place they pick
in "Make room for the destination", not from a clock time they have to guess:

1. **Deadline.** The place's closing time that day, minus the visit (60 min for
   food, 90 min otherwise), becomes the plan's `end_time`. With split hours,
   the deadline uses the earliest opening window still reachable. A place with
   no opening hours on record, or one open 24 hours, gets no deadline.
2. **Trim.** The trip is replanned with the repair loop in make-room mode. All
   three optional stop kinds may be skipped, and keeping them is not offered,
   because the traveller chose this activity over a coffee stop. If even
   skipping everything arrives too late, the result is `wont_fit` and the
   frontend leaves the trip unchanged.
3. **Fill.** With at least 45 spare minutes, the route agent runs in fill mode
   on the longest open stretch of road, skipping 10% of the stretch at each end.
   The agent starts from a query based on the traveller's learned signals. Code
   keeps only places it saw in a search that are open at arrival and where
   `detour + 30 min ≤ spare time`. The result is a **suggestion** the
   traveller can add with one click; the agent never adds stops itself. If the
   agent finds nothing, the planner's own candidates are tried first. Otherwise
   the panel says the agent found nothing worth the detour and shows its trace.

The response adds `make_room: {status, deadline, closes_at, arrival,
spare_minutes, suggestion}`. A plain plan request is unchanged and makes no
extra LLM calls. This gives the same agent two ways in: the traveller can ask
it directly ("Ask for a better fit"), or the planner can call it when there's
time to spend.

### Learned preferences (OKF)

Profile preferences and feedback events (`POST /profiles/events`) become
learned signals; saved trips appear as trip history in the OKF document
(they are not used to derive signals). The signals are `local_food`,
`quiet_low_crowd_stops`, `scenic_views`, and `budget_conscious`. Each signal records its source (`profile`, `behaviour`, or
both) and evidence count. The Travel profile page shows them under "What
VibeTrip has learned about you"; "Not me" (shown for behaviour-only signals) records a
`signal_dismissed` event, and the signal stays off until new behaviour evidence
arrives; signals that also come from the profile are removed by editing the
preferences. The OKF Markdown
document handed to the LLM is rebuilt from the database and cached until its
inputs change.

### Supporting services

- **Reroute (`POST /trips/reroute`)** recomputes geometry through the edited
  stops as ordered waypoints.
- **Trip simulator (`POST /trips/simulate`)** applies a closure, crowd spike,
  or late-running event and picks a feasible backup.
- **Storage** uses Postgres when `DATABASE_URL` is set; on a connection failure
  it logs a warning, uses process memory for a 30-second cool-down, then
  retries.

New response fields (all additive): `repair_log` on `/trips/plan`;
`agent_source`, `agent_rationale`, `agent_trace` on `/trips/search`;
`learned_signals` on `/profiles/okf`.

### Observability (optional)

Set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` to send LangChain and
LangGraph traces to LangSmith. It is off by default. Enabling it sends prompts,
including the traveller's OKF profile, to LangSmith's servers.

## Deploying the MVP

The hosted demo runs the FastAPI backend on Railway and the Vite frontend on
Vercel. Vercel forwards `/api/*` to the backend (`vercel.json`), so the browser
talks to one origin: the session cookie stays first-party (Safari blocks
cross-site cookies) and no CORS change is needed.

**Backend (Railway)** builds from `Dockerfile`. Dependencies install with
`constraints.txt`, the exact versions the test suite passes with, so transitive
packages cannot drift in the image. The project has a Postgres service and a
volume mounted at `/data`. Backend variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `VIBETRIP_AUTH_SECRET` | long random value |
| `VIBETRIP_COOKIE_SECURE` | `true` (HTTPS only) |
| `VIBETRIP_AUTH_FILE` / `VIBETRIP_MEDIA_DIR` / `VIBETRIP_OKF_DIR` | `/data/auth_users.json`, `/data/media`, `/data/okf` |
| `OPENAI_API_KEY`, `GOOGLE_MAPS_API_KEY`, `VIBETRIP_LIVE_MAPS_ENABLED`, other `VIBETRIP_*` | as in `.env.example` |

```bash
railway up --service backend --ci
```

**Frontend (Vercel)** needs `VITE_API_URL=/api` plus the `VITE_GOOGLE_MAPS_*`
values, then:

```bash
vercel deploy --prod
```

The server Maps key cannot be IP-restricted on Railway (no static outbound IP),
so restrict it to the Routes and Places APIs, keep the browser key separate and
referrer-restricted, and set spending caps on both Google Cloud and OpenAI: the
in-process rate limits are per minute, not a budget.

Uploaded memories also need persistent object storage or a persistent volume in
deployment. The current media adapter writes to `backend/media/`, so ephemeral
hosting will lose uploads after a restart. Replace it with S3, Cloudflare R2,
or another sharable object store before treating the app as production-ready.

Before publishing a repository or demo, confirm that `.env`, API keys, local
auth data, OKF artifacts, media, and database volumes are not committed. The
repository's `.gitignore` excludes these local state files.
