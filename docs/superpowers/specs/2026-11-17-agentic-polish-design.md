# VibeTrip interview polish: agentic route assistant, repair loop, and cleanup

Date: 2026-11-17 · Branch: `interview-polish` · Deadline: interview Thu 2026-11-19

## Intent

Ernest is walking through VibeTrip in a job interview on Thursday. Today the
README calls it "agentic", but the code is a linear five-node LangGraph
workflow with one optional LLM ranking call. An informed interviewer would
call that a workflow, not an agent. The goal is that every claim in the
README and the walkthrough survives probing:

- the project has **real agency** in two bounded places (the LLM decides
  what happens next), with deterministic code still owning correctness;
- the obvious weak spots (no tests, silent storage fallback, unpinned
  dependencies, an unreadable `day_builder`, a pass-through `route_scout`,
  an OKF file nobody reads) are fixed rather than explained away.

## Goals

1. **Tool-calling route assistant agent** (behind `POST /trips/search`).
2. **LLM repair loop** in the planner graph when `day_builder` produces a
   warning (this also delivers "conditional edge", item #4).
3. Cleanup items: pinned deps, Postgres retry, signal provenance fix, pytest
   suite, `day_builder` refactor, `route_scout` owns the provider call, OKF
   cache, Profile "what VibeTrip learned" UI, README reword.
4. Optional LangSmith tracing, off by default.

## Non-goals

- Agent that edits the whole itinerary (option B, rejected: double the
  scope, too risky for Thursday). The user still picks one stop and clicks
  "Replace selected".
- Streaming agent progress to the UI.
- Splitting `src/App.jsx`.
- Moving the post-graph reroute loop (`main.py:350`) into the graph.
- Vector store, new auth, deployment changes.

## Anti-goals (failure even if it "works")

- **Breaking demo mode.** The app must remain fully usable with no Google key
  and no OpenAI key. Every LLM path falls back to today's deterministic
  behaviour.
- **LLM owning facts.** The agent and the repair node must never produce
  coordinates, route segments, opening hours, prices, or place IDs that a
  tool did not return.
- **Unbounded cost.** A looping agent must not multiply Google or OpenAI
  calls without a hard cap.
- **Behaviour drift from the refactor.** `day_builder` output must be
  identical before and after the refactor for the same input.

## Constraints

- Python 3.13, FastAPI, LangGraph 1.2.9, langchain-core 1.4.9,
  langchain-openai 1.3.5, langsmith 0.10.5 already installed in `.venv`.
- Existing guards stay authoritative: Google circuit breakers
  (`providers._reserve_google_request`), the LLM search per-minute limiter
  (`search_intent._search_request_available`), and segment filtering
  (`providers._candidate_in_route_segment`).
- Response shapes consumed by the frontend must stay backward compatible;
  new fields are additive.
- Work on branch `interview-polish`; `main` stays demo-ready. Run the README
  manual checklist plus `npm run build`, `python3 -m compileall -q backend`,
  and the new pytest suite before merging.

## Approaches considered (route assistant agent)

| Approach | Trade-off | Decision |
|---|---|---|
| **1. Hand-written `StateGraph`: agent node → tool node → conditional "continue?" edge** | Explicit, readable in one file, real use of LangGraph branching and loops; slightly more code | **Chosen** by Ernest |
| 2. LangGraph prebuilt `create_react_agent` | ~10 lines, but the loop is a black box in an interview; harder to customise caps and trace | Rejected |
| 3. Hand-rolled `bind_tools` + `while` loop, no LangGraph | Max control, but makes LangGraph look pointless elsewhere | Rejected |

Repair loop: one sensible way (conditional edge after `day_builder`), agreed.
On route mode, Ernest chose **never switch mode, only skip optional stops**
over "allow switching" (which would override the user's choice, need a
provider refetch, and need frontend mode sync).

## Design

### A. Route assistant agent (`backend/route_agent.py`, new)

**User-facing behaviour (option A, chosen):** same assistant card. User picks
a stop and types a request. The agent searches, checks opening hours at the
stop's arrival time, checks cost against budget, broadens and retries if
nothing fits, then returns a shortlist plus a short rationale and a visible
step trace. The user still clicks "Replace selected"; that flow (reroute,
feedback event) is unchanged.

**Graph:** `agent` (LLM with bound tools) → conditional edge → `tools`
(executes tool calls) → back to `agent`; ends when the LLM calls
`submit_shortlist`, emits no tool call, or the step cap is hit.

**State** (TypedDict): messages, request context (fixed by the API, not
the LLM), `seen_candidates: dict[id, candidate]`, `trace: list[step]`,
`step_count`, `search_count`, final `shortlist_ids` and `rationale`.

**Tools** (all wrap existing code; the LLM only supplies the arguments shown):

| Tool | LLM supplies | Does |
|---|---|---|
| `search_places(query, category)` | free-text Places query + category (`restaurant`/`cafe`/`fuel`/`scenic`/`other`) | Calls a provider search with the segment bounds, budget, crowd tolerance and route mode **fixed from the request**. Adds results to `seen_candidates`. Returns compact summaries (id, name, category, rating, detour, cost label, crowd risk). |
| `check_open_at_arrival(place_ids)` | ids | Uses the same opening-hours logic as `day_builder` (`_opening_status_at`, moved to a shared module) against the selected stop's arrival date/time. Returns open / closed / unknown per id. |
| `check_budget(place_ids)` | ids | Compares each candidate's cost to (a) the cost of the stop being replaced and (b) the traveller's remaining budget. Returns e.g. "SGD 8 cheaper than current stop; within remaining SGD 140" or unknown. |
| `submit_shortlist(place_ids, rationale)` | ids + one sentence | Terminal. Ids not in `seen_candidates` are dropped, and **code also drops any id `check_open_at_arrival` would mark closed** (checked even if the agent never called the tool). |

**Provider changes for the agent (my call):** today
`search_route_places` squashes free text through
`_normalize_place_search_query` ("quiet cafe with a view" and "cozy coffee
spot" both become `cafe coffee`), so a "broaden and retry" would resend the
same query. Add an agent-only path (new keyword args, deterministic path
unchanged): send the agent's text query to Places as-is, apply the category
filter from the agent's declared `category` instead of re-deriving it, keep
segment and locality filtering exactly as today. Fetch the route geometry
**once per agent run** and reuse it across searches (today each search
spends a Routes call).

**Budget inputs (my call):** `RoutePlaceSearchRequest` gains optional
`current_stop_cost_sgd` and `remaining_budget_per_person_sgd`, computed by
the frontend from the selected stop and its existing cost breakdown. Missing
→ `check_budget` returns unknown.

**Caps:** max 3 `search_places` calls and max 8 total agent steps per run;
overall wall-clock timeout (reuse `VIBETRIP_LLM_TIMEOUT_SECONDS` budget,
builder picks the exact composition). Each run consumes one slot of the
existing LLM search per-minute limiter. Google calls still go through the
existing circuit breakers.

**Fallback (deterministic):** if no OpenAI key, LLM disabled, limiter
exhausted, timeout, exception, or empty validated shortlist → run today's
pipeline exactly (`parse_place_search_intent` + `provider.search_route_places`).
Partial agent results are discarded on fallback.

**API changes (additive):**
- `RoutePlaceSearchRequest` gains optional `arrival_time` (HH:MM) and
  `arrival_date` (YYYY-MM-DD) for the selected stop. Frontend sends them from
  the selected stop. If missing, `check_open_at_arrival` returns "unknown".
- Response gains `agent_source` (`"agent"` | `"deterministic"`),
  `agent_rationale` (string | null), and `agent_trace` (list of
  `{step, tool, summary}` with human-readable summaries such as
  *"Searched 'quiet cafe' → 5 results, 2 in this leg"*). `candidate_places`
  keeps its shape: the validated shortlist first, in agent order, then other
  seen in-segment candidates that aren't closed at arrival (my call; the UI
  shows the top 4).

**Frontend:** in `RouteAssistant` (`src/components/PlannerPage.jsx`), under
the results, a collapsible "How the agent got here" list rendering
`agent_trace`, plus the rationale line. Hidden when `agent_source` is
`deterministic`. The live pill text reflects the source.

### B. Planner repair loop (`backend/graph.py`)

**Decided (Ernest): the repair loop never changes the user's route mode.**
It only skips optional stop kinds. If that can't fix the warning, it keeps
the warning and adds a suggestion ("Try Fastest to arrive earlier").

- **Which warnings are repairable:** only the late-arrival warning.
  The "fastest has no fuel stop" warning cannot be fixed by skipping stops,
  so it is never repaired.
- **Skip mechanism (my call):** new state field `skipped_stop_kinds: set`,
  respected inside `day_builder` when it builds planned stops (that is where
  stop kinds are chosen; `selected_places` alone doesn't control it).
  Optional kinds: `coffee`, `attraction`, second `fuel`. **Never skipped:**
  `meal` and the only fuel stop.
- **Feasibility pre-check (my call):** before repairing, compute arrival with
  every optional kind skipped. If that is still late, don't repair: record
  `accept_warning` with reason "unfixable without changing route" plus the
  mode suggestion. Prevents stripping stops from trips that were always going
  to warn (e.g. long drives where drive time + buffer already passes
  `end_time`).
- **Graph:** conditional edge after `day_builder`: repairable warning and
  `repair_attempts < 2` and feasible → `repair`; else → END. `repair` edges
  back to `day_builder` (not `detour_reviewer`; candidate selection is
  unchanged by a skip).
- **`repair` node:** the LLM (structured output, Pydantic `Literal` enum)
  picks **one** action from `skip_coffee`, `skip_attraction`,
  `skip_extra_fuel`, `accept_warning` (only those whose kind is actually
  in the current itinerary are offered), given the warning, the current
  itinerary summary, and the traveller profile/learned preferences, plus a
  one-sentence reason. This is the personalised decision (an adventurous
  traveller keeps the lookout and drops coffee). Without an LLM, rule order:
  coffee → extra fuel → attraction.
- **Keep the best version (my call):** snapshot each attempt; final result is
  the best by (number of warnings, arrival offset), not simply the last.
- **Post-reroute check (my call):** `main.py`'s reroute loop calls
  `day_builder` again with real detour-inclusive drive times. After that loop,
  run the same repair step (shared function, same caps, same
  `skipped_stop_kinds` carried in state) so that `repair_log` always
  describes the warning the user actually sees.
- **Output:** `repair_log` entries `{attempt, warning, action, reason,
  source: "llm" | "rule"}` returned in `/trips/plan` (additive), shown as a
  small note under the existing warning in the planner.

### C. `route_scout` owns the provider call

Move the provider call (and its demo fallback/warning) from
`main.py:plan_trip` into `route_scout`. Graph becomes async (`ainvoke`).
`route_scout` also sets `candidate_places` and `provider`/`provider_warning`
in state. The provider instance is passed via LangGraph config/context, not
a global, so tests can inject `DemoMapsProvider`. The post-graph reroute loop
stays in `main.py` and keeps using the same provider.

### D. Cleanup items

1. **Pin deps.** `package.json`: replace every `"latest"` with the exact
   version in `package-lock.json`. `requirements.txt`: pin to the installed
   versions. Add `requirements-dev.txt` with `pytest` (and `pytest-asyncio`
   if needed).
2. **Postgres retry.** Replace the one-way `_postgres_disabled` latch in
   `TripRepository` and `ContextEventRepository` with a shared connection
   helper: on failure, log a warning and skip Postgres for a cool-down
   (~30 s), then retry. Remove the duplicated `_connect` code.
3. **Signal provenance.** In `user_context.build_user_context`, each learned
   signal gets `source`: `profile` (from an explicit preference),
   `behaviour` (from feedback events), or `both`, plus the existing
   `evidence_count`. The OKF render shows the source. Confidence for
   profile-only signals stays at the base value. Fixes the confusing
   "evidence 0" line.
4. **Tests (pytest, `backend/tests/`).** Written **before** the
   `day_builder` refactor and run against current behaviour first. Cover:
   `day_builder` (ordering by route progress, opening-hours skip, fastest
   requires fuel, multi-day dates, buffer maths), `_score_place`,
   `_candidate_in_route_segment`, `_safe_llm_intent`, `build_user_context`
   provenance, repair-loop routing (with a fake LLM and the rule fallback),
   and the route agent (fake chat model scripting tool calls; assert ID
   validation, caps, and fallback). No test calls Google or OpenAI.
5. **`day_builder` refactor.** Split into named helpers (pick stops, build
   planned stops, schedule, arrival/warnings) and named constants for the
   durations and offsets. Output must match the pre-refactor tests exactly.
6. **OKF cache.** In `OKFProfileExporter.export`, compute a fingerprint of
   profile + trip ids/updated_at + event ids. If unchanged since the last
   export for that owner, return the cached result and skip the file write.
   In-process cache only.
7. **Profile UI: "What VibeTrip has learned about you."** New card on
   `ProfileView`. Loads via the existing `POST /profiles/okf`. Lists each
   signal with its label, source ("from your profile" / "learned from your
   trips"), and evidence count. Each behaviour-sourced signal has a
   "Not me" button that records a `signal_dismissed` event via
   `POST /profiles/events`; `build_user_context` excludes dismissed signals
   until newer behaviour evidence arrives after the dismissal. Profile-sourced
   signals are changed by toggling the preference itself, as today.
8. **README.** Rewrite the agent section: the planner is a workflow with two
   bounded agentic parts (route assistant agent, repair loop); explain the
   "deterministic owns correctness" boundary; document new response fields,
   LangSmith, tests, and how to run them. Remove claims the code doesn't back.

### E. LangSmith (optional)

Add to `.env.example`, commented out and off by default:
`LANGSMITH_TRACING=false`, `LANGSMITH_API_KEY=`, `LANGSMITH_PROJECT=vibetrip`.
No code changes beyond making sure nothing breaks when unset. README notes
that enabling it sends prompts, including the OKF profile, to LangSmith.

## Implementation order

Pin deps → Postgres retry → signal provenance → tests against current
behaviour → `day_builder` refactor → `route_scout` async → repair loop →
route agent (backend, then frontend trace) → OKF cache → Profile UI →
LangSmith env → README → full verification (build, compileall, pytest,
manual checklist with and without keys).

## Left to the builder

- Exact tool return formats, trace summary wording, and prompt text.
- Timeout composition and whether caps are env-configurable.
- Fake chat model choice for tests (e.g. a scripted `BaseChatModel`
  subclass if langchain's fakes don't support `bind_tools`).
- Exact UI placement and styling of the trace, repair notes, and the
  learned-signals card, following existing classes in `src/styles.css`.
- Whether `_opening_status_at` moves to a new module or stays in `graph.py`
  and is imported.
