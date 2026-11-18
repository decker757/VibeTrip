# Make Room for the Destination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adding a destination place replans the trip against a deadline taken from the place's opening hours. The plan trims stops if the trip runs late. If there's spare time, the route agent suggests one stop to fill it.

**Architecture:**
- **Deadline:** a new `backend/make_room.py` derives the deadline and builds the `make_room` response.
- **Trimming:** `repair.py` gets a `make_room_mode` flag that allows three skips and never offers `accept_warning`.
- **Filling:** `route_agent.py` gets a `fill` mode with its own prompt and a code-enforced fit check.
- **Endpoint:** `/trips/plan` wires these together when `destination_activity` is sent.
- **Frontend:** the client separates fetching a plan from applying it, so a `wont_fit` response leaves the trip untouched. The client also renders the status and the suggestion in the "Make room for the destination" panel.

**Tech Stack:** FastAPI, LangGraph, pytest (asyncio auto mode), React and Vite. There is no frontend test runner: verify frontend work with `npm run build` and a browser check.

**Spec:** `docs/superpowers/specs/2026-11-18-make-room-time-budget-design.md`

## Global Constraints

- Work only in the worktree `/Users/ernesttan/Documents/VibeTrip-make-room` on branch `feature/make-room-time-budget`. Never deploy.
- Don't add AI attribution to commits: no `Co-Authored-By` trailers and no "Generated with" lines.
- Visit time is 60 min for food (category contains restaurant, cafe, food or bakery) and 90 min for everything else.
- The fill trigger is spare time of at least 45 min. A fill stop lasts 30 min. Fit rule: `detour_minutes + 30 ≤ spare_minutes`, and `detour_minutes` is not doubled.
- In make-room mode the cap is 3 repair attempts. Otherwise it stays at 2.
- Closing times after midnight are capped at 23:59 on the start date.
- A plain `/trips/plan` call, without `destination_activity`, must behave exactly as it does today and make no extra LLM calls.
- All 90 existing backend tests keep passing: `.venv/bin/python -m pytest -q` from the worktree root. If the worktree has no `.venv`, use `/Users/ernesttan/Documents/VibeTrip/.venv/bin/python`.

## Review Focus

1. **Split hours** (11:00–14:00 and 17:00–22:00) with an arrival of 15:00 should pick the evening window and give a deadline of 20:30 for a 90-minute visit. This is tested in Task 1.
2. **The only window has already closed** (it closes 13:00 and the current arrival is 15:05). The result should be `wont_fit`, never a silent add. Tested in Task 1 (the last period is chosen) and in Task 4 (the endpoint returns `wont_fit`).
3. **The LLM picks `accept_warning` in make-room mode.** That action is never offered, and the rule-based trim runs instead. Tested in Task 2.
4. **A fill candidate whose detour plus stop time exceeds the spare time** is dropped even if the agent shortlists it. Tested in Task 3.
5. **No `destination_activity`.** The response has no `make_room` key and the plan is unchanged. Tested in Task 4.

---

### Task 1: Deadline from opening hours

**Files:**
- Create: `backend/make_room.py`
- Test: `backend/tests/test_make_room.py`

**Interfaces:**
- Produces:
  - `VISIT_MINUTES_FOOD = 60`
  - `VISIT_MINUTES_DEFAULT = 90`
  - `visit_minutes(place: dict) -> int`
  - `destination_deadline(place: dict, on: date, current_arrival: datetime | None) -> Deadline | None`
  - `@dataclass Deadline(deadline: datetime, closes_at: datetime, visit_minutes: int)`
  - A `None` return means `no_hours`.

Google periods use `day` with 0 = Sunday, so map with `(on.weekday() + 1) % 7`, matching `opening_hours.opening_status_at`. Only periods whose `open.day` is that day count. A `close` on a different day caps at 23:59. A period with no `close` means open 24 hours, so return `None`.

- [ ] **Step 1: Write the failing tests** (`ON = date(2026, 11, 20)`, a Friday, so Google day 5)

```python
def period(open_h, close_h, day=5, close_day=None):
    return {"open": {"day": day, "hour": open_h, "minute": 0}, "close": {"day": close_day if close_day is not None else day, "hour": close_h, "minute": 0}}

def place(*periods, category="Art Museum"):
    return {"id": "p", "name": "P", "category": category, "opening_hours": {"periods": list(periods)}}

def test_single_window_deadline_is_close_minus_visit():
    d = destination_deadline(place(period(10, 17)), ON, datetime(2026, 11, 20, 13, 40))
    assert d.deadline == datetime(2026, 11, 20, 15, 30) and d.closes_at.hour == 17 and d.visit_minutes == 90

def test_food_visit_is_60_minutes():
    assert destination_deadline(place(period(10, 22), category="Food Court"), ON, None).deadline.hour == 21

def test_split_hours_picks_first_window_still_reachable():
    d = destination_deadline(place(period(11, 14), period(17, 22)), ON, datetime(2026, 11, 20, 15, 0))
    assert d.deadline == datetime(2026, 11, 20, 20, 30)

def test_no_reachable_window_uses_last_window():
    d = destination_deadline(place(period(9, 13)), ON, datetime(2026, 11, 20, 15, 5))
    assert d.deadline == datetime(2026, 11, 20, 11, 30)

def test_after_midnight_close_is_capped():
    d = destination_deadline(place(period(18, 2, close_day=6)), ON, None)
    assert d.closes_at == datetime(2026, 11, 20, 23, 59)

def test_open_24_hours_has_no_deadline():
    assert destination_deadline(place({"open": {"day": 0, "hour": 0, "minute": 0}}), ON, None) is None

def test_no_periods_that_day_has_no_deadline():
    assert destination_deadline(place(period(10, 17, day=1)), ON, None) is None
    assert destination_deadline({"id": "p", "opening_hours": {}}, ON, None) is None
```

- [ ] **Step 2: Run them and confirm they fail**
  Run: `python -m pytest backend/tests/test_make_room.py -q`
  Expected: FAIL with an ImportError.

- [ ] **Step 3: Implement `Deadline`, `visit_minutes` and `destination_deadline`** in `backend/make_room.py`.

- [ ] **Step 4: Run the tests and confirm they pass**
  Run: `python -m pytest backend/tests/test_make_room.py -q`
  Expected: all pass.

- [ ] **Step 5: Commit**
  Message: `Derive a destination deadline from its opening hours`

---

### Task 2: Make-room mode in the repair loop

**Files:**
- Modify: `backend/repair.py`, which gets `MAX_MAKE_ROOM_ATTEMPTS = 3`.
  - `should_repair` uses `_attempt_cap(state)`.
  - `repair_step` offers `[*skips]` without `"accept_warning"` when `state.get("make_room_mode")`.
- Modify: `backend/graph.py`. Add `make_room_mode: bool` to `PlannerState`. Undeclared keys are dropped between nodes, so the flag must be declared to survive.
- Test: `backend/tests/test_repair.py`

**Interfaces:**
- Produces: the state key `make_room_mode: bool`, which defaults to absent/False and leaves today's behaviour unchanged.
- Produces: `_attempt_cap(state: dict) -> int`.

- [ ] **Step 1: Write the failing tests** in `test_repair.py`, reusing `FakeStructuredModel` and the `demo_state` fixture.

```python
def test_make_room_mode_never_offers_accept_warning(demo_state, monkeypatch):
    model = FakeStructuredModel(RepairDecision(action="accept_warning", reason="keep all"))
    monkeypatch.setattr("backend.repair.llm_enabled", lambda: True)
    monkeypatch.setattr("backend.repair.get_chat_model", lambda: model)
    out = run_graph({**demo_state("balanced", "14:30"), "make_room_mode": True})
    assert out["route"]["warnings"] == []
    assert all(e["action"] != "accept_warning" for e in out["repair_log"])
    assert all(e["source"] == "rule" for e in out["repair_log"])

def test_make_room_mode_allows_a_third_attempt():
    late = {"route": {"warnings": [{"code": "late_arrival", "message": "late"}]}, "itinerary": [{"kind": "coffee"}], "repair_attempts": 2}
    assert should_repair(late) == "finalize"
    assert should_repair({**late, "make_room_mode": True}) == "repair"
```

  Import `should_repair` from `backend.repair`.

- [ ] **Step 2: Run them and confirm they fail**
  Run: `python -m pytest backend/tests/test_repair.py -q`
  Expected: the two new tests fail. In the first, the LLM's `accept_warning` is accepted. In the second, `should_repair` returns `finalize`.

- [ ] **Step 3: Implement** `_attempt_cap`, the action filter in `repair_step`, and the `PlannerState` key.

- [ ] **Step 4: Run the full suite and confirm it passes**
  Run: `python -m pytest -q`
  Expected: 90 existing tests plus the new ones pass.

- [ ] **Step 5: Commit**
  Message: `Let make-room repairs trim every optional stop and never keep them at the activity's expense`

---

### Task 3: Fill mode in the route agent

**Files:**
- Modify: `backend/route_agent.py`
- Test: `backend/tests/test_route_agent.py`

**Interfaces:**
- Produces:
  - `RouteAgentContext` gets two new trailing fields with defaults: `mode: Literal["replace", "fill"] = "replace"` and `spare_minutes: int | None = None`.
  - `FILL_STOP_MINUTES = 30`
  - `fits_spare(place: dict, spare_minutes: int) -> bool`. It returns `float(place.get("detour_minutes") or 0) + FILL_STOP_MINUTES <= spare_minutes`.
  - `FILL_SYSTEM_PROMPT`, the fill-mode version of `SYSTEM_PROMPT`. Copy its rules, but the first line reads: "You help a road-tripper add one stop to a leg of their drive. They have {spare} spare minutes; the stop takes about 30 minutes plus its detour." Keep the {spare} placeholder and fill it in when building the prompt.
- Consumes: none.
- Changes:
  - `_initial_state(ctx)` picks the prompt by `ctx.mode`.
  - `_request_message(ctx)` in fill mode says "Adding a stop between {previous_stop_title} and {next_stop_title}; {spare_minutes} spare minutes" instead of "Replacing: …".
  - `_validated_candidates` takes `ctx` and, in fill mode with `spare_minutes` set, also requires `fits_spare`. Change its signature to `_validated_candidates(shortlist_ids, seen, ctx)` and read `ctx.arrival` from it.

- [ ] **Step 1: Write the failing tests**
  Use `ctx(...)`, then `dataclasses.replace(c, mode="fill", spare_minutes=N)`. Demo detours: coffee 3, attraction 14, lunch 12, fuel 2.

```python
async def test_fill_mode_drops_shortlisted_places_that_do_not_fit():
    fill = replace(ctx(), mode="fill", spare_minutes=40)  # 14 + 30 > 40 drops the attraction
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "scenic", "category": "scenic"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-attraction", "demo-coffee"], "rationale": "r"}, id="2")])
    result = await run_route_agent(fill, DemoMapsProvider(), model=model)
    ids = [c["id"] for c in result.candidates]
    assert "demo-attraction" not in ids and ids[0] == "demo-coffee"

async def test_fill_mode_uses_fill_prompt():
    fill = replace(ctx(), mode="fill", spare_minutes=90)
    state = _initial_state(fill)
    assert "add one stop" in state["messages"][0].content and "90 spare minutes" in state["messages"][1].content

def test_fits_spare_counts_detour_once():
    assert fits_spare({"detour_minutes": 15}, 45) and not fits_spare({"detour_minutes": 16}, 45)
```

  Check how `ScriptedChatModel` is used in the existing happy-path test and follow the same pattern. Search results must come from `DemoMapsProvider.search_places_text`. If the demo search for "scenic" doesn't return `demo-coffee`, change the test query or category so that both ids are seen, and keep the assertion intent unchanged.

- [ ] **Step 2: Run them and confirm they fail**
  Run: `python -m pytest backend/tests/test_route_agent.py -q`
  Expected: the new tests fail. Existing tests pass.

- [ ] **Step 3: Implement** the fields, the prompt, the message, `fits_spare`, and the `_validated_candidates` change.

- [ ] **Step 4: Run the tests and confirm they pass**
  Run: `python -m pytest backend/tests/test_route_agent.py -q`
  Expected: all pass. All existing replace-mode tests are unchanged.

- [ ] **Step 5: Commit**
  Message: `Add a fill mode to the route agent that only suggests stops fitting the spare time`

---

### Task 4: Wire make-room into `/trips/plan`

**Files:**
- Modify: `backend/make_room.py`. Add the gap finder, the query, the deterministic fill, and the response builder.
- Modify: `backend/main.py`:
  - `TripRequest` gets `destination_activity: dict | None = None` and `current_arrival_time: str | None = None`.
  - Factor the three gates at the top of `_try_route_agent` (search enabled, agent env flag, rate-limit slot) into `_route_agent_allowed() -> bool`, then reuse it.
  - Change `plan_trip` as described in Step 3.
- Test: `backend/tests/test_make_room.py`, which gets endpoint tests using `auth_client`.

**Interfaces:**
- Consumes:
  - From Task 1: `destination_deadline`, `Deadline`.
  - From Task 2: the `make_room_mode` state key.
  - From Task 3: `RouteAgentContext(mode="fill", spare_minutes=…)`, `run_route_agent`, `fits_spare`.
- Produces, in `make_room.py`:
  - `FILL_TRIGGER_MINUTES = 45`
  - `longest_gap(itinerary: list[dict], distance_km: float) -> tuple[float, float]`. Gaps run between consecutive `route_progress_km` values, with 0 and `distance_km` as endpoints. Items without progress are skipped.
  - `fill_query(learned_preferences: list[str]) -> str`. The first match, in this order: `scenic_views` → "scenic viewpoint or nature stop", `local_food` → "local food spot", `quiet_low_crowd_stops` → "quiet low-crowd stop". Otherwise "worthwhile stop".
  - `deterministic_fill(candidates: list[dict], gap: tuple[float, float], used_ids: set[str], spare_minutes: int) -> dict | None`. It picks the highest `enjoyment_score` among along-route, plannable candidates that aren't in `used_ids`, whose progress is inside the gap, and that pass `fits_spare`.
  - `async build_make_room(result: dict, request: TripRequest, deadline: Deadline | None, provider, agent_allowed: bool) -> dict`. It returns `{status, destination_place_id, deadline, closes_at, arrival, spare_minutes, suggestion}`:
    - `deadline`, `closes_at` and `arrival` are `"HH:MM"` or `None`.
    - `suggestion` is `None` or `{candidates, rationale, trace, source}`.
    - `status` is `no_hours` when `deadline` is `None`, `wont_fit` when the arrival is after the deadline, and `fits` otherwise.
    - Fill runs only when the status is `fits` and spare time is at least 45 min.
    - The agent context is built from the request plus the gap, with `target_progress_km` at the gap's midpoint. `arrival` is the time at the previous stop (or the start), and `query` is `fill_query(...)`.
    - If the agent returns `None`, fall back to `deterministic_fill`, wrapped as `{candidates: [pick], rationale: <one line naming the pick and the spare time>, trace: [], source: "deterministic"}`.

- [ ] **Step 1: Write the failing tests.**
  The demo plan arrives at 15:05 with every stop, and trims to 14:30 or earlier by skipping coffee and attraction. That's the existing `test_fixable_late_trip…` fixture.

```python
BODY = {"start": "Singapore", "destination": "KL", "start_date": "2026-11-20", "current_arrival_time": "15:05"}

def test_plain_plan_has_no_make_room(auth_client):
    assert "make_room" not in auth_client.post("/trips/plan", json=BODY).json()

def test_fits_with_trim_against_real_deadline(auth_client):
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": place(period(10, 16))}).json()  # deadline 14:30
    assert r["make_room"]["status"] == "fits" and r["make_room"]["deadline"] == "14:30"
    assert [e["action"] for e in r["repair_log"]] == ["skip_coffee", "skip_attraction"]

def test_closed_before_arrival_wont_fit(auth_client):
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": place(period(9, 13))}).json()  # deadline 11:30
    assert r["make_room"]["status"] == "wont_fit"

def test_no_hours_plans_with_default_end_time(auth_client):
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": {"id": "x", "name": "X", "opening_hours": {}}}).json()
    assert r["make_room"]["status"] == "no_hours" and r["repair_log"] == []

def test_spare_time_runs_agent_fill(auth_client, monkeypatch):
    async def fake_agent(context, provider, model=None):
        assert context.mode == "fill" and context.spare_minutes >= 45
        return RouteAgentResult(candidates=[{"id": "demo-coffee", "name": "C", "detour_minutes": 3}], rationale="fits", trace=[{"step": 1}])
    monkeypatch.setattr("backend.make_room.run_route_agent", fake_agent)
    monkeypatch.setattr("backend.main._route_agent_allowed", lambda: True)
    r = auth_client.post("/trips/plan", json={**BODY, "destination_activity": place(period(10, 21))}).json()  # deadline 19:30
    assert r["make_room"]["status"] == "fits" and r["make_room"]["spare_minutes"] >= 45
    assert r["make_room"]["suggestion"]["source"] == "agent"

def test_longest_gap_and_fill_query():
    items = [{"route_progress_km": 65}, {"route_progress_km": 125}, {"route_progress_km": 300}]
    assert longest_gap(items, 340) == (125, 300)
    assert fill_query(["local_food", "scenic_views"]) == "scenic viewpoint or nature stop"
    assert fill_query([]) == "worthwhile stop"
```

  These reuse `place` and `period` from Task 1's tests. If the demo plan's untrimmed arrival isn't 15:05 when run through the endpoint, check it with one `/trips/plan` call and adjust only the open/close hours so that each test's scenario holds.

- [ ] **Step 2: Run them and confirm they fail**
  Run: `python -m pytest backend/tests/test_make_room.py -q`
  Expected: the new tests fail.

- [ ] **Step 3: Implement the `make_room.py` additions and the `main.py` changes.**
  In `plan_trip`, when `request.destination_activity` is set:
  1. Parse `current_arrival_time` on `start_date`.
  2. Compute the deadline.
  3. If there is one, put `end_time = deadline.strftime("%H:%M")` and `make_room_mode = True` into `state` before `planner_graph.ainvoke`.
  4. After the reroute loop, set `response["make_room"] = await build_make_room(result, request, deadline, provider, _route_agent_allowed())`.
  
  `_route_agent_allowed()` reserves a rate-limit slot, so call it only when fill would actually run. Pass a callable, or check `fits` and the spare time before calling it.

- [ ] **Step 4: Run the full suite and confirm it passes**
  Run: `python -m pytest -q`
  Expected: everything passes.

- [ ] **Step 5: Commit**
  Message: `Replan against the destination's deadline and let the agent fill spare time`

---

### Task 5: Frontend flow and panel

**Files:**
- Modify: `src/App.jsx`
- Modify: `src/components/PlannerPage.jsx`, specifically the destination panel inside the route grid at about line 33.
- Modify: `src/app/formatters.js`
- Modify: `src/styles.css`

**Interfaces:**
- Consumes from Task 4: the response's `make_room` object.
- Produces:
  - `insertStopByProgress(stops: Stop[], stop: Stop) -> Stop[]` in `formatters.js`. It inserts before the first non-stay stop with a larger `route_progress_km`, and otherwise before the stay.
  - State in `App.jsx`: `makeRoom` (`{place, ...make_room}` or null), `isMakingRoom` (bool), and `stopsEditedRef`.

- [ ] **Step 1: Split `generateTrip`.**
  - Move the fetch into `async function requestPlan(overrides = {}) -> result`. It builds the same request body and adds `destination_activity` and `current_arrival_time` when `overrides.destinationActivity` is given.
  - Move the state updates from the success branch into `applyPlanResult(result, { routeMode, travellers })`.
  - `generateTrip` = `applyPlanResult(await requestPlan(overrides), …)` with the existing catch and finally. It also resets `makeRoom` to null and `stopsEditedRef.current` to false.
  - Set `stopsEditedRef.current = true` in `selectCandidate`, `removeStop`, `addStop`, and the replace path.

- [ ] **Step 2: Add `async function makeRoomForDestination(candidate)`.**
  - **Multi-day:** if `route.estimated_trip_days > 1`, call the existing `addDestinationCandidate(candidate)`, set the message "Deadlines apply to same-day arrivals only, so <name> was added without one.", and return.
  - **Edited stops:** if `stopsEditedRef.current` is true and `!window.confirm("Adding <name> replans the trip around its opening hours and resets your stop edits. Continue?")`, return.
  - Set `isMakingRoom`, then call `requestPlan({ destinationActivity: candidate, currentArrivalTime: route.estimated_arrival_time })`.
  - **`wont_fit`:** don't apply anything. Set the message "You'd arrive <arrival>, after <name> closes at <closes>. Start earlier or pick another place." The `closes` value is `make_room.closes_at`.
  - **Otherwise:** `applyPlanResult(result, …)`, then `setMakeRoom({ place: candidate, ...result.make_room })`, then insert the destination before check-in using the stops from the result. Refactor `addDestinationCandidate`'s insertion body into `insertDestinationStop(baseStops, candidate)` and reuse it in both places.
  - On any error, fall back to the old `addDestinationCandidate(candidate)` with the message "Couldn't check opening hours; added without a deadline."

- [ ] **Step 3: Wire the panel.**
  - Destination rows call `makeRoomForDestination`. The row button shows "Checking…" while `isMakingRoom` is true.
  - When `makeRoom` is set, show a status line above the rows:
    - `fits`: "✓ <name> added · closes <closes_at> · arrive by <deadline> · you arrive <arrival>, <spare as Xh Ym> to spare".
    - `no_hours`: "<name> added · no opening hours on record, so no deadline".
  - When `makeRoom.suggestion` exists, show a card with:
    - the first candidate's name, category and "<detour> min detour · 30 min stop";
    - the rationale;
    - an **Add to route** button that calls `addSuggestedStop(candidate)`, which runs `insertStopByProgress` and then `rerouteDraft`;
    - a `<details>` "How the agent got here" with the trace, shown only when `source === "agent"`. Copy the existing `.agent-trace` markup from `RouteAssistant`.
  - Add styles in the panel's existing visual language. Reuse `.agent-rationale` and `.agent-trace` where possible.

- [ ] **Step 4: Build and confirm it passes**
  Run: `npm run build`
  Expected: the build succeeds with no errors.

- [ ] **Step 5: Commit**
  Message: `Replan around a destination's opening hours and show the agent's fill suggestion in the panel`

---

### Task 6: End-to-end check and README

**Files:**
- Modify: `README.md`. Add a short "Make room for the destination" section next to the route agent section, covering the deadline, the trim, the fill, and the fact that the agent only suggests.

- [ ] **Step 1: Run the app locally with live keys.**
  1. Symlink `.env` from the main checkout: `ln -s /Users/ernesttan/Documents/VibeTrip/.env .env`. The symlink is gitignored, so don't commit it.
  2. Start the API with uvicorn on port 8010 and Vite with `VITE_API_URL=http://localhost:8010`.
  3. Plan Phoenix, AZ → Los Angeles, CA on Balanced, starting at 08:10.
  4. Add a destination place that has opening hours.
  
  Expected: the status line appears. If there is at least 45 min to spare, a suggestion appears, and its trace shows when the agent ran. Adding the suggestion puts it at its route position.

- [ ] **Step 2: Check the `wont_fit` path.**
  Start at 14:00 and add a museum. Expected: the trip is unchanged and the closing-time message shows.

- [ ] **Step 3: Run the full suite and the build**
  Run: `python -m pytest -q && npm run build`
  Expected: both pass.

- [ ] **Step 4: Commit**
  Message: `Document make-room planning`
