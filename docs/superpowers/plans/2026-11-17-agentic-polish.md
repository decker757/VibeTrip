# Agentic Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make VibeTrip honestly agentic in two bounded places (a tool-calling route assistant and an LLM repair loop) and fix the weak spots an interviewer would probe.

**Architecture:** The planner stays a LangGraph workflow, with real branching added. `route_scout` fetches from the provider, and a conditional edge after `day_builder` loops through a `repair` node that skips optional stop kinds. A separate hand-written LangGraph agent (`agent` → `tools` → conditional edge) handles `/trips/search`. Deterministic code owns facts and validates everything, and every LLM path falls back to today's behaviour.

**Tech Stack:** Python 3.13, FastAPI 0.139, LangGraph 1.2.9, langchain-core 1.4.9, langchain-openai 1.3.5, pytest, React 19 + Vite 8.

**Spec:** `docs/superpowers/specs/2026-11-17-agentic-polish-design.md`

## Global Constraints

- Branch `interview-polish`. Never commit to `main`. Commit messages carry **no AI attribution** (no `Co-Authored-By` naming a model, no "Generated with" lines).
- Demo mode must keep working with **no Google key and no OpenAI key**. Every LLM path falls back to today's deterministic behaviour.
- The LLM must never produce coordinates, segments, opening hours, prices, or place IDs that a tool did not return.
- Agent caps: max **3** `search_places` calls and **8** agent steps per run. Each run consumes one slot of the existing LLM search per-minute limiter. Google calls still go through `_reserve_google_request`.
- Repair loop: never changes `route_mode`. Max **2** repair attempts per plan (shared by graph and post-reroute). Never skips `meal` or the only fuel stop.
- Response shapes stay backward compatible. New fields are additive only.
- No test calls Google or OpenAI. Tests run with `OPENAI_API_KEY` and `GOOGLE_MAPS_API_KEY` unset.
- Run all Python commands from repo root `/Users/ernesttan/Documents/VibeTrip` with `.venv/bin/python`.
- Final verification: `npm run build`, `.venv/bin/python -m compileall -q backend`, `.venv/bin/python -m pytest -q`, `git diff --check`, plus the README manual checklist with and without keys.

## Review Focus

1. **The model fails partway through an agent run** (raises, times out, or returns no tool call on step 1). `/trips/search` returns the deterministic results, with `agent_source: "deterministic"` and no partial agent candidates. Test in Task 10.
2. **The replaced stop has no arrival time or route progress** (e.g. a reopened saved trip). The agent still runs, `check_open_at_arrival` returns `unknown`, and nothing crashes. Test in Task 9.
3. **The trip runs late even with every optional stop skipped** (e.g. `end_time` 12:00 on a 229-minute drive). No stops are stripped, and `repair_log` holds one `accept_warning` with the "Try Fastest" suggestion. Test in Task 7.
4. **A signal is dismissed, then new matching behaviour arrives** after the dismissal. The signal comes back as `behaviour`. Test in Task 3.
5. **Postgres fails once, then recovers.** The repository uses Postgres again after the cool-down instead of staying on memory forever. Test in Task 2.

---

### Task 1: Pin dependencies and add the test harness

**Files:**
- Modify: `package.json`, `requirements.txt`
- Create: `requirements-dev.txt`, `pytest.ini`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_smoke.py`

**Interfaces:**
- Produces: fixture `demo_state(route_mode: str = "balanced", end_time: str = "18:00") -> dict` in `conftest.py`. It returns a planner state built from `DemoMapsProvider().plan_trip("A", "B", 400, "medium", "08:10", route_mode)`, with `start_date="2026-11-20"`, `start_time="08:10"`, `adventure_level=70`. Fixture `auth_client` returns a FastAPI `TestClient(app)` with `get_current_user` overridden to `{"id": "test-user", "display_name": "Tester", "home_base": "Singapore", "email": "t@example.com"}`.

- [ ] **Step 1: Pin `package.json`.** Use the exact versions from `package-lock.json`: `vite 8.1.4`, `react 19.2.7`, `react-dom 19.2.7`, `@vitejs/plugin-react 6.0.3`, `@googlemaps/js-api-loader 2.1.1`.
- [ ] **Step 2: Pin `requirements.txt` with `==`.** Versions: `fastapi 0.139.0`, `python-multipart 0.0.32`, `langchain 1.3.13`, `langchain-openai 1.3.5`, `langgraph 1.2.9`, `uvicorn[standard] 0.51.0`, `httpx 0.28.1`, `psycopg[binary] 3.3.4`.
- [ ] **Step 3: Set up pytest.** Create `requirements-dev.txt` containing `-r requirements.txt`, `pytest`, `pytest-asyncio`. Run `.venv/bin/pip install pytest pytest-asyncio`, then pin both to the installed versions. Create `pytest.ini` with `testpaths = backend/tests` and `asyncio_mode = auto`.
- [ ] **Step 4: Write `conftest.py`.** An autouse fixture uses `monkeypatch` to:
  - delete `OPENAI_API_KEY` and `GOOGLE_MAPS_API_KEY`;
  - set `VIBETRIP_LIVE_MAPS_ENABLED=false`;
  - point `VIBETRIP_OKF_DIR` at `tmp_path`, set **before** importing `backend.okf`; if the module was already imported, patch `backend.okf.OKF_ROOT` instead.

  Also add the `demo_state` and `auth_client` fixtures from Interfaces.
- [ ] **Step 5: Write a smoke test.** Add `test_health(auth_client)` asserting `GET /health` returns 200. Run `.venv/bin/python -m pytest -q`. Expected: 1 passed.
- [ ] **Step 6: Verify the frontend and commit.** Run `npm install && npm run build`. Expected: build succeeds. Commit with the message `Pin dependencies and add pytest harness`.

### Task 2: Postgres connector with cool-down instead of a one-way latch

**Files:**
- Create: `backend/db.py`
- Modify: `backend/storage.py` (both `_connect` methods, and every `self._postgres_disabled = True`)
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces: `class PostgresConnector(cooldown_seconds: float = 30.0, clock: Callable[[], float] = time.monotonic)` with:
  - `connect() -> Connection | None`: returns `None` when `DATABASE_URL` is unset, when psycopg is missing, or during the cool-down;
  - `mark_failed(error: Exception) -> None`: logs `logger.warning` and starts the cool-down.

  The schema is ensured once per successful process connection. `TripRepository` and `ContextEventRepository` each hold one `PostgresConnector`, and `_postgres_disabled` is removed.

- [ ] **Step 1: Write the failing tests.**
```python
def test_no_database_url_returns_none(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert PostgresConnector().connect() is None

def test_failure_then_recovery_after_cooldown(monkeypatch):
    now = [0.0]
    attempts = []
    def fake_connect(url, connect_timeout):
        attempts.append(now[0])
        if len(attempts) == 1:
            raise OSError("down")
        return FakeConnection()
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setattr("backend.db._psycopg_connect", fake_connect)
    connector = PostgresConnector(cooldown_seconds=30, clock=lambda: now[0])
    assert connector.connect() is None          # first attempt fails
    now[0] = 10; assert connector.connect() is None and len(attempts) == 1   # in cool-down, no retry
    now[0] = 31; assert connector.connect() is not None and len(attempts) == 2
```
  `FakeConnection` is a test double with `cursor()` (a context manager whose `execute` is a no-op), `commit()` and `close()`. `_psycopg_connect` is a module-level wrapper around `psycopg.connect`, so it can be patched.
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_db.py -v`. Expected: FAIL with `ModuleNotFoundError: backend.db`.
- [ ] **Step 3: Implement `PostgresConnector`** in `backend/db.py`. Replace both repositories' `_connect` with `self._db.connect()`, and replace every `self._postgres_disabled = True` in `except` blocks with `self._db.mark_failed(error)`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** with the message `Retry Postgres after a cool-down instead of disabling it for the process lifetime`.

### Task 3: Signal provenance and dismissal

**Files:**
- Modify: `backend/user_context.py` (`build_user_context`, `_feedback_signals`), `backend/okf.py` (`render_profile_okf` signal lines)
- Test: `backend/tests/test_user_context.py`

**Interfaces:**
- Produces: each entry in `context["learned_signals"]` has keys `signal: str`, `label: str` (taken from the existing `signal_labels`), `source: Literal["profile", "behaviour", "both"]`, `evidence_count: int` and `confidence: float`. Dismissal events have `event_type == "signal_dismissed"` and `data == {"signal": <name>}`.

- [ ] **Step 1: Write the failing tests.**
```python
def test_profile_only_signal_is_labelled_profile():
    ctx = build_user_context({"preferences": ["local-gems"]})
    s = next(x for x in ctx["learned_signals"] if x["signal"] == "local_food")
    assert s["source"] == "profile" and s["evidence_count"] == 0 and s["confidence"] == 0.55

def test_behaviour_signal_counts_evidence():
    events = [{"id": "1", "event_type": "chatbot_search", "data": {"query": "quiet cafe"}, "created_at": "2026-11-01T00:00:00+00:00"}]
    s = build_user_context({}, events=events)["learned_signals"][0]
    assert (s["signal"], s["source"], s["evidence_count"]) == ("quiet_low_crowd_stops", "behaviour", 1)

def test_both_sources():
    events = [{"id": "1", "event_type": "chatbot_search", "data": {"query": "local food"}, "created_at": "2026-11-01T00:00:00+00:00"}]
    s = next(x for x in build_user_context({"preferences": ["local-gems"]}, events=events)["learned_signals"] if x["signal"] == "local_food")
    assert s["source"] == "both"

def test_dismissed_behaviour_signal_is_excluded():
    events = [
        {"id": "1", "event_type": "chatbot_search", "data": {"query": "quiet cafe"}, "created_at": "2026-11-01T00:00:00+00:00"},
        {"id": "2", "event_type": "signal_dismissed", "data": {"signal": "quiet_low_crowd_stops"}, "created_at": "2026-11-02T00:00:00+00:00"},
    ]
    assert "quiet_low_crowd_stops" not in build_user_context({}, events=events)["learned_preferences"]

def test_newer_evidence_after_dismissal_relearns():   # Review Focus 4
    events = [
        {"id": "1", "event_type": "chatbot_search", "data": {"query": "quiet cafe"}, "created_at": "2026-11-01T00:00:00+00:00"},
        {"id": "2", "event_type": "signal_dismissed", "data": {"signal": "quiet_low_crowd_stops"}, "created_at": "2026-11-02T00:00:00+00:00"},
        {"id": "3", "event_type": "chatbot_search", "data": {"query": "low crowd lookout"}, "created_at": "2026-11-03T00:00:00+00:00"},
    ]
    s = next(x for x in build_user_context({}, events=events)["learned_signals"] if x["signal"] == "quiet_low_crowd_stops")
    assert s["source"] == "behaviour" and s["evidence_count"] == 1

def test_dismissal_keeps_profile_source():
    events = [{"id": "2", "event_type": "signal_dismissed", "data": {"signal": "local_food"}, "created_at": "2026-11-02T00:00:00+00:00"}]
    s = next(x for x in build_user_context({"preferences": ["local-gems"]}, events=events)["learned_signals"] if x["signal"] == "local_food")
    assert s["source"] == "profile"

def test_okf_renders_source():
    doc = render_profile_okf(build_user_context({"preferences": ["local-gems"]}), timestamp="t")
    assert "local_food (from profile" in doc
```
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_user_context.py -v`. Expected: FAIL with `KeyError: 'source'` and assertion failures.
- [ ] **Step 3: Implement it.** Behaviour evidence counts only events created after the latest `signal_dismissed` for that signal. `_feedback_signals` returns `[]` for `signal_dismissed` events. Confidence is `0.55 + 0.12 * evidence_count`, capped at `0.95`, as today. The OKF line format is `- {signal} (from {profile|behaviour|profile + behaviour}; confidence {c:.2f}; evidence {n})`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** with the message `Record where each learned signal came from and support dismissing signals`.

### Task 4: Characterisation tests for current planner behaviour

These tests pin **today's** behaviour before the refactor, so they pass immediately. That is expected; there is no failing step.

**Files:**
- Create: `backend/tests/test_day_builder.py`, `backend/tests/test_providers.py`, `backend/tests/test_search_intent.py`, `backend/tests/fixtures/day_builder_golden.json`

**Interfaces:**
- Consumes: the `demo_state` fixture (Task 1).

- [ ] **Step 1: Generate the golden file.** For each of `fastest`, `balanced` and `scenic`, and for each `end_time` in `18:00` and `12:00`, save `day_builder(detour_reviewer(vibe_matcher(demo_state(mode, end_time))))` keeping only the `itinerary` and `route` keys. Write the script inline in the test module as a `__main__` block so it can be re-run, then run it once.
- [ ] **Step 2: Write the tests.**
```python
@pytest.mark.parametrize("mode,end_time", [(m, e) for m in ("fastest","balanced","scenic") for e in ("18:00","12:00")])
def test_matches_golden(mode, end_time, demo_state): ...   # itinerary equals golden exactly; golden route keys are a subset of route (later tasks add keys)

def test_balanced_order_follows_route_progress(demo_state):
    kinds = [i["kind"] for i in run(demo_state("balanced"))["itinerary"]]
    assert kinds == ["coffee", "fuel", "attraction", "meal", "stay"]

def test_fastest_has_fuel_and_no_coffee(demo_state):
    kinds = [i["kind"] for i in run(demo_state("fastest"))["itinerary"]]
    assert "fuel" in kinds and "coffee" not in kinds

def test_closed_at_arrival_is_skipped(demo_state):
    # give demo-coffee opening periods that close at 08:00 on the trip day; coffee must disappear
    ...

def test_late_arrival_warning(demo_state):
    assert "later than your target end time of 12:00" in run(demo_state("balanced", "12:00"))["route"]["schedule_warning"]

def test_multi_day_metadata(demo_state):
    s = demo_state("balanced"); s["route"] = {**s["route"], "drive_minutes": 1500, "distance_km": 2000}
    stay = run(s)["itinerary"][-1]
    assert stay["day_number"] >= 2 and stay["date"] > "2026-11-20"
```
  `test_providers.py` covers `_candidate_in_route_segment` (lower bound inclusive, upper bound exclusive, `None` progress rejected when bounds are set) and `_score_place` (a closed place scores lower than the same place open, and a fastest-mode detour of more than 8 min is penalised). `test_search_intent.py` covers `_safe_llm_intent`: a locality the user never wrote is replaced by the fallback hint.
- [ ] **Step 3: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 4: Commit** with the message `Add characterisation tests for planner, providers, and search intent`.

### Task 5: Refactor `day_builder`, extract opening hours, add structured warnings

**Files:**
- Create: `backend/opening_hours.py`
- Modify: `backend/graph.py:68-103` (move out), `backend/graph.py:224-378` (`day_builder`)
- Test: `backend/tests/test_day_builder.py` (add tests)

**Interfaces:**
- Produces:
  - `opening_hours.opening_status_at(place: dict, arrival: datetime) -> bool | None` and `opening_hours.candidate_is_plannable(place: dict) -> bool`. These are moved verbatim; `graph.py` imports them.
  - `day_builder` additionally sets `route["warnings"]: list[{"code": "late_arrival" | "fastest_no_fuel", "message": str}]` and `route["arrival_offset_minutes"]: int`. `route["schedule_warning"]` stays the space-joined messages, or `None`.
  - Named constants in `graph.py`: `COFFEE_MINUTES = 25`, `FUEL_MINUTES = 15`, `ATTRACTION_MINUTES = {"balanced": 45, "scenic": 60}`, `MEAL_MINUTES = 55`, `FIRST_LEG_MIN_MINUTES = 60`, `MIN_LEG_GAP_MINUTES = 25`, `ATTRACTION_MIN_DRIVE = 180`, `MEAL_MIN_DRIVE = 210`, `SECOND_FUEL_MIN_DRIVE = 360`, `BUFFER_RATIO = 0.2`, `MIN_BUFFER_MINUTES = 20`.

- [ ] **Step 1: Write the failing tests.**
```python
def test_structured_late_warning(demo_state):
    route = run(demo_state("balanced", "12:00"))["route"]
    assert [w["code"] for w in route["warnings"]] == ["late_arrival"]
    assert route["arrival_offset_minutes"] == 415      # 08:10 -> 15:05

def test_no_warnings_list_empty(demo_state):
    assert run(demo_state("balanced"))["route"]["warnings"] == []
```
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_day_builder.py -v`. Expected: the 2 new tests FAIL with `KeyError: 'warnings'`.
- [ ] **Step 3: Refactor.** Split `day_builder` into module-level helpers:
  - `_pick_stop_options(state) -> StopOptions`, a dataclass holding the meal, coffee, fuel, extra fuel, scenic and meal options;
  - `_build_planned_stops(options, meal, fuel, route_mode, drive_minutes) -> list[PlannedStop]`;
  - `_schedule_stops(planned, start, drive_minutes, distance_km) -> ScheduleResult`;
  - `_arrival_and_warnings(...)`.

  `day_builder` becomes orchestration. Replace magic numbers with the constants. **Golden tests must still pass unchanged.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass, including the golden tests.
- [ ] **Step 5: Commit** with the message `Refactor day_builder into named steps and return structured warnings`.

### Task 6: `route_scout` owns the provider call (async graph)

**Files:**
- Modify: `backend/graph.py` (`route_scout`, `PlannerState`), `backend/main.py:319-349` (`plan_trip`)
- Test: `backend/tests/test_graph.py`

**Interfaces:**
- Consumes: `DemoMapsProvider`, `get_maps_provider()`.
- Produces: `async def route_scout(state: PlannerState, config: RunnableConfig) -> PlannerState`. It reads `config["configurable"]["maps_provider"]`. If that is absent, it keeps today's pass-through behaviour. On a provider exception it falls back to `DemoMapsProvider` with today's warning text. It sets `route`, `candidate_places`, `provider_name: str` and `provider_warning: str | None`. `plan_trip` calls `await planner_graph.ainvoke(state, config={"configurable": {"maps_provider": provider}})` and switches its reroute provider to `DemoMapsProvider()` when `result["provider_name"] == "demo"`.

- [ ] **Step 1: Write the failing tests.**
```python
async def test_route_scout_uses_injected_provider():
    out = await planner_graph.ainvoke(base_request_state(), config={"configurable": {"maps_provider": DemoMapsProvider()}})
    assert out["provider_name"] == "demo" and out["candidate_places"]

async def test_route_scout_falls_back_on_provider_error():
    class Boom:
        async def plan_trip(self, *a, **k): raise RuntimeError("x")
    out = await planner_graph.ainvoke(base_request_state(), config={"configurable": {"maps_provider": Boom()}})
    assert out["provider_name"] == "demo" and "Maps provider unavailable (RuntimeError)" in out["provider_warning"]

def test_plan_endpoint_still_works(auth_client):
    r = auth_client.post("/trips/plan", json={"start": "Singapore", "destination": "Kuala Lumpur", "start_date": "2026-11-20"})
    assert r.status_code == 200 and r.json()["itinerary"][-1]["kind"] == "stay"
```
  `base_request_state()` is a local helper returning the `TripRequest` defaults as a dict, with `start` and `destination` set and no `route` or `candidate_places`.
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_graph.py -v`. Expected: FAIL (`provider_name` missing).
- [ ] **Step 3: Implement it** as described in Interfaces. Remove the provider call from `plan_trip`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** with the message `Move the provider call into route_scout and run the planner graph async`.

### Task 7: LLM repair loop

**Files:**
- Create: `backend/repair.py`
- Modify: `backend/graph.py` (`day_builder` honours `skipped_stop_kinds`; graph edges), `backend/main.py` (reroute loop and response), `src/App.jsx` (keep `repair_log`), `src/components/PlannerPage.jsx` (repair note)
- Test: `backend/tests/test_repair.py`

**Interfaces:**
- Consumes: `route["warnings"]` and `route["arrival_offset_minutes"]` (Task 5); `get_chat_model()` and `llm_enabled()` from `recommender.py`.
- Produces, in `backend/repair.py`:
  - `RepairAction = Literal["skip_coffee", "skip_attraction", "skip_extra_fuel", "accept_warning"]`
  - `class RepairDecision(BaseModel): action: RepairAction; reason: str`
  - `available_actions(state) -> list[RepairAction]`: one skip action per optional kind present in the itinerary (`coffee` → `skip_coffee`, `attraction` → `skip_attraction`, a second `fuel` → `skip_extra_fuel`), plus `accept_warning`.
  - `should_repair(state) -> Literal["repair", "finalize"]`: `"repair"` only when there is a `late_arrival` warning, `repair_attempts < 2`, `repair_settled` is not true, and at least one skip action is available.
  - `repair.py` must not import `graph.py` (graph imports repair, so that would be a cycle); `rebuild` is always passed in.
  - `repair_step(state, rebuild: Callable[[dict], dict]) -> dict`. `rebuild` is used only for the feasibility check. First it runs the feasibility check: rebuild with every available kind skipped. If that is still late, it logs `accept_warning` with reason `"Unfixable without changing route mode"` and `source "rule"`, sets `repair_settled = True`, and appends `" Try Fastest to arrive earlier."` to `route.schedule_warning` when `route_mode != "fastest"`. Otherwise it chooses an action (the LLM with structured output, given the warning, the itinerary summary, `learned_preferences` and `adventure_level`; an invalid or failed LLM answer falls back to the rule order coffee → extra fuel → attraction), adds the kind to `skipped_stop_kinds`, increments `repair_attempts`, saves a snapshot of `{itinerary, route}` in `repair_snapshots`, and appends to `repair_log`.
  - `finalize_best(state) -> dict`: chooses the best of the current state and the snapshots by `(len(route["warnings"]), route["arrival_offset_minutes"])`.
  - `repair_until_settled(state, rebuild: Callable[[dict], dict]) -> dict`: loops `should_repair` → `repair_step` → `rebuild`, then `finalize_best`. `main.py` uses this after the reroute.
  - `repair_log` entries are `{"attempt": int, "warning": str, "action": RepairAction, "reason": str, "source": "llm" | "rule"}`.
  - `day_builder` reads `state.get("skipped_stop_kinds", [])`, a JSON list drawn from `"coffee"`, `"attraction"` and `"extra_fuel"`.
  - Graph: `day_builder` → conditional `should_repair` → `repair` (registered as `lambda s: repair_step(s, day_builder)`) → `day_builder`; `"finalize"` → `finalize` (`finalize_best`) → END.
  - The `/trips/plan` response gains `repair_log: list` (additive).

- [ ] **Step 1: Write the failing tests** (LLM disabled by the conftest unless a test patches `get_chat_model`).
```python
def test_fixable_late_trip_skips_stops_and_clears_warning(demo_state):
    out = run_graph(demo_state("balanced", "14:30"))          # arrives 15:05 today
    assert out["route"]["warnings"] == []
    assert [e["action"] for e in out["repair_log"]][0] == "skip_coffee"
    kinds = [i["kind"] for i in out["itinerary"]]
    assert "meal" in kinds and "fuel" in kinds

def test_unfixable_trip_is_not_stripped(demo_state):          # Review Focus 3
    out = run_graph(demo_state("balanced", "12:00"))
    assert [i["kind"] for i in out["itinerary"]] == ["coffee", "fuel", "attraction", "meal", "stay"]
    assert [e["action"] for e in out["repair_log"]] == ["accept_warning"]
    assert out["route"]["schedule_warning"].endswith("Try Fastest to arrive earlier.")

def test_no_optional_stops_means_no_repair(demo_state):
    out = run_graph(demo_state("fastest", "12:00"))
    assert out["repair_log"] == [] and out["route"]["warnings"][0]["code"] == "late_arrival"

def test_never_changes_route_mode(demo_state):
    assert run_graph(demo_state("scenic", "14:30"))["route"]["route_mode"] == "scenic"

def test_llm_choice_is_used(demo_state, monkeypatch):
    monkeypatch.setattr("backend.repair.llm_enabled", lambda: True)
    monkeypatch.setattr("backend.repair.get_chat_model", lambda: FakeStructuredModel(RepairDecision(action="skip_attraction", reason="r")))
    out = run_graph(demo_state("balanced", "14:30"))
    assert out["repair_log"][0] == {"attempt": 1, "warning": ANY, "action": "skip_attraction", "reason": "r", "source": "llm"}

def test_invalid_llm_action_falls_back_to_rule(demo_state, monkeypatch):
    # model returns skip_extra_fuel when no second fuel stop exists -> rule picks skip_coffee, source "rule"
    ...

def test_finalize_keeps_best_snapshot():
    # snapshot with 0 warnings beats current state with 1 warning
    ...
```
  `run_graph(state)` calls `asyncio.run(planner_graph.ainvoke(state))` (the graph has an async node since Task 6) (`route_scout` passes through without a provider). `FakeStructuredModel` implements `with_structured_output(schema)` and returns an object whose `invoke` returns the preset decision.
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_repair.py -v`. Expected: FAIL with `ModuleNotFoundError: backend.repair`.
- [ ] **Step 3: Implement `repair.py`, `day_builder`'s `skipped_stop_kinds` support, and the graph edges.**
- [ ] **Step 4: Wire it into `main.py`.** Inside the existing 3-iteration reroute loop, after `day_builder`, call `repair_until_settled(result, day_builder)` before comparing waypoint ids. Add `repair_log` to the response.
- [ ] **Step 5: Add an endpoint test.**
```python
def test_plan_returns_repair_log(auth_client):
    r = auth_client.post("/trips/plan", json={"start": "Singapore", "destination": "KL", "start_date": "2026-11-20", "end_time": "12:00"})
    assert r.json()["repair_log"][0]["action"] == "accept_warning"
```
- [ ] **Step 6: Frontend.** In `generateTrip`, store `result.repair_log || []` in new state `repairLog`, and pass it to `PlannerPage` through `form`. In `PlannerPage`, below the `live-message`, render one line per entry, `{reason}` prefixed by "Adjusted:" for skip actions or "Kept as is:" for `accept_warning`, using a new `.repair-note` class in `src/styles.css` styled like `.live-message` but muted. Render nothing when the list is empty.
- [ ] **Step 7: Run the tests and confirm everything passes.** Run `.venv/bin/python -m pytest -q && npm run build`. Expected: all pass, and the build succeeds.
- [ ] **Step 8: Commit** with the message `Add a bounded repair loop that skips optional stops when a trip runs late`.

### Task 8: Provider search path for the agent

**Files:**
- Modify: `backend/providers.py` (`DemoMapsProvider`, `GoogleMapsProvider.search_route_places`)
- Test: `backend/tests/test_providers.py` (add tests)

**Interfaces:**
- Produces:
  - `@dataclass RouteGeometry: route: dict; points: list[tuple[float, float]]; distance_km: float`
  - `CATEGORY_FILTER_PHRASES = {"restaurant": "restaurant", "cafe": "cafe coffee", "fuel": "gas station convenience store", "scenic": "scenic attraction", "other": ""}`
  - On both providers:
    - `async def route_geometry(self, start: str, destination: str, route_mode: str) -> RouteGeometry`
    - `async def search_places_text(self, geometry: RouteGeometry, text_query: str, filter_query: str, location_hint: str | None, budget_per_person: int, crowd_tolerance: str, route_mode: str, segment_start_progress_km: float | None, segment_end_progress_km: float | None, target_progress_km: float | None) -> list[dict]`: the Places text search with **today's** segment, intent (`filter_query`) and locality filters, sorted by `_sort_route_matches`.
  - `GoogleMapsProvider.search_route_places` is re-implemented as `route_geometry` + `search_places_text(maps_query, normalized_query, location_hint, ...)`, with identical behaviour.
  - The demo `search_places_text` filters the demo candidates by segment, `filter_query` and `location_hint`. It does **not** require free-text term matches, so a broader query can return more results.

- [ ] **Step 1: Write the failing tests.**
```python
async def test_demo_text_search_respects_segment():
    p = DemoMapsProvider(); g = await p.route_geometry("A", "B", "balanced")
    ids = [c["id"] for c in await p.search_places_text(g, "cozy coffee spot", "cafe coffee", None, 400, "medium", "balanced", 0, 100, 65)]
    assert ids == ["demo-coffee"]

async def test_demo_text_search_other_category_returns_all_in_segment():
    p = DemoMapsProvider(); g = await p.route_geometry("A", "B", "balanced")
    ids = {c["id"] for c in await p.search_places_text(g, "anything nice", "", None, 400, "medium", "balanced", 100, 210, None)}
    assert ids == {"demo-fuel", "demo-attraction", "demo-lunch"}

async def test_google_search_route_places_uses_one_routes_call(monkeypatch):
    # patch httpx.AsyncClient.post to record URLs and return canned JSON; assert exactly one GOOGLE_ROUTES_URL call
    ...
```
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_providers.py -v`. Expected: FAIL with `AttributeError: route_geometry`.
- [ ] **Step 3: Implement it** as described in Interfaces.
- [ ] **Step 4: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass, including the Task 4 provider tests.
- [ ] **Step 5: Commit** with the message `Split route geometry from place text search so callers can reuse one route`.

### Task 9: Route assistant agent graph

**Files:**
- Create: `backend/route_agent.py`, `backend/tests/fakes.py`
- Modify: `backend/search_intent.py` (rename `_search_request_available` to the public `reserve_llm_search_slot`, and update the caller)
- Test: `backend/tests/test_route_agent.py`

**Interfaces:**
- Consumes: `RouteGeometry`, `route_geometry`, `search_places_text` and `CATEGORY_FILTER_PHRASES` (Task 8); `opening_status_at` (Task 5); `_extract_location_hint` (providers).
- Produces:
  - `@dataclass RouteAgentContext`: `start`, `destination`, `budget_per_person: int`, `crowd_tolerance`, `route_mode`, `segment_start_progress_km`, `segment_end_progress_km`, `target_progress_km`, `arrival: datetime | None`, `current_stop_cost_sgd: float | None`, `remaining_budget_per_person_sgd: float | None`, `selected_stop_title`, `previous_stop_title`, `next_stop_title`, `query: str`.
  - `@dataclass RouteAgentResult`: `candidates: list[dict]`, `rationale: str`, `trace: list[dict]`, where each trace entry is `{"step": int, "tool": str, "summary": str}`.
  - `async def run_route_agent(context: RouteAgentContext, provider, model=None) -> RouteAgentResult | None`. It returns `None` (meaning the caller should fall back) on any exception, on a timeout of `VIBETRIP_AGENT_TIMEOUT_SECONDS` (default `20`), or when the validated shortlist is empty. `model` defaults to `get_chat_model()`.
  - Tool argument schemas (Pydantic, passed to `model.bind_tools`):
    - `SearchPlaces(query: str, category: Literal["restaurant", "cafe", "fuel", "scenic", "other"])`
    - `CheckOpenAtArrival(place_ids: list[str])`
    - `CheckBudget(place_ids: list[str])`
    - `SubmitShortlist(place_ids: list[str], rationale: str)`
  - Constants: `MAX_SEARCHES = 3`, `MAX_STEPS = 8`, `MAX_SHORTLIST = 4`.
  - Graph: `StateGraph(AgentState)` with nodes `agent` and `tools`; conditional edge `route_after_agent(state) -> Literal["tools", "__end__"]`. It ends on `SubmitShortlist`, on no tool call, or when `step_count >= MAX_STEPS`. A 4th `SearchPlaces` call returns a tool message saying the search limit was reached, without calling the provider. Route geometry is fetched once, lazily, on the first search.
  - Post-processing in code: drop ids the agent never saw, drop ids where `opening_status_at(place, arrival) is False`, keep the shortlist order, then append other seen candidates that passed both checks, deduplicated.
  - `check_budget` summary format: `"{name}: SGD {d} cheaper|more than current stop; within|over remaining SGD {r}"`, using `"unknown"` for missing values.

- [ ] **Step 1: Write `fakes.py`.** `ScriptedChatModel(responses: list[AIMessage])` subclasses `BaseChatModel`. `bind_tools` returns `self`, each `_generate` call pops the next response, and it records the received messages in `self.calls`.
- [ ] **Step 2: Write the failing tests.**
```python
def ai_tool(name, args, id="1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id}])

async def test_happy_path_returns_shortlist_and_trace():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "quiet cafe", "category": "cafe"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"], "rationale": "Quiet and on the way."}, "2")])
    r = await run_route_agent(ctx(segment=(0, 100)), DemoMapsProvider(), model)
    assert r.candidates[0]["id"] == "demo-coffee" and r.rationale == "Quiet and on the way."
    assert [t["tool"] for t in r.trace] == ["SearchPlaces", "SubmitShortlist"]

async def test_unseen_ids_are_dropped():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "cafe", "category": "cafe"}),
                               ai_tool("SubmitShortlist", {"place_ids": ["made-up", "demo-coffee"], "rationale": "x"}, "2")])
    r = await run_route_agent(ctx(segment=(0, 100)), DemoMapsProvider(), model)
    assert [c["id"] for c in r.candidates] == ["demo-coffee"]

async def test_closed_at_arrival_dropped_even_without_check():
    # provider stub whose demo-coffee has periods closed at ctx.arrival; agent submits it; result is None (empty shortlist)
    ...

async def test_search_cap():
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": f"q{i}", "category": "other"}, str(i)) for i in range(4)]
                              + [ai_tool("SubmitShortlist", {"place_ids": ["demo-fuel"], "rationale": "x"}, "9")])
    provider = CountingDemoProvider()
    await run_route_agent(ctx(segment=(100, 210)), provider, model)
    assert provider.search_calls == 3 and provider.geometry_calls == 1

async def test_step_cap_returns_none():
    model = ScriptedChatModel([ai_tool("CheckBudget", {"place_ids": []}, str(i)) for i in range(10)])
    assert await run_route_agent(ctx(), DemoMapsProvider(), model) is None

async def test_model_exception_returns_none():
    class Broken(ScriptedChatModel):
        def _generate(self, *a, **k): raise RuntimeError("down")
    assert await run_route_agent(ctx(), DemoMapsProvider(), Broken([])) is None

async def test_missing_arrival_and_progress_still_runs():      # Review Focus 2
    model = ScriptedChatModel([ai_tool("SearchPlaces", {"query": "cafe", "category": "cafe"}),
                               ai_tool("CheckOpenAtArrival", {"place_ids": ["demo-coffee"]}, "2"),
                               ai_tool("SubmitShortlist", {"place_ids": ["demo-coffee"], "rationale": "x"}, "3")])
    r = await run_route_agent(ctx(segment=(None, None), arrival=None, target=None), DemoMapsProvider(), model)
    assert r is not None and "unknown" in r.trace[1]["summary"]

async def test_budget_summary():
    # CheckBudget on demo-lunch (SGD 22) with current_stop_cost_sgd=30, remaining=140 -> "SGD 8 cheaper than current stop; within remaining SGD 140"
    ...
```
  `ctx(...)` is a local helper building a `RouteAgentContext` with defaults (`start="A"`, `destination="B"`, budget 400, `"medium"`, `"balanced"`, arrival `datetime(2026, 11, 20, 10, 0)`).
- [ ] **Step 3: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_route_agent.py -v`. Expected: FAIL with `ModuleNotFoundError: backend.route_agent`.
- [ ] **Step 4: Implement `route_agent.py`.** The system prompt must say: choose only ids returned by tools; the segment, opening hours and budget are enforced by code; broaden the query or category if nothing fits; call `SubmitShortlist` with at most 4 ids and one sentence.
- [ ] **Step 5: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit** with the message `Add a tool-calling LangGraph agent for route place requests`.

### Task 10: Wire the agent into `/trips/search` and show the trace

**Files:**
- Modify: `backend/main.py` (`RoutePlaceSearchRequest`, `search_route_places`), `src/App.jsx` (`searchRoutePlaces`), `src/components/PlannerPage.jsx` (`RouteAssistant`), `src/styles.css`
- Test: `backend/tests/test_search_endpoint.py`

**Interfaces:**
- Consumes: `run_route_agent`, `RouteAgentContext` (Task 9); `reserve_llm_search_slot`, `_llm_search_enabled` (search_intent).
- Produces:
  - Request adds optional `arrival_time: str | None` (HH:MM), `arrival_date: str | None` (YYYY-MM-DD), `current_stop_cost_sgd: float | None` and `remaining_budget_per_person_sgd: float | None`.
  - Response adds `agent_source: "agent" | "deterministic"`, `agent_rationale: str | None` and `agent_trace: list`.
  - The agent runs when `_llm_search_enabled()`, `VIBETRIP_ROUTE_AGENT_ENABLED` (default `"true"`) is not falsy, and `reserve_llm_search_slot()` succeeds. Otherwise, or when it returns `None`, today's path runs unchanged.

- [ ] **Step 1: Write the failing tests.**
```python
def test_search_without_llm_is_deterministic(auth_client):
    body = {"start": "A", "destination": "B", "query": "a quiet cafe", "segment_start_progress_km": 0, "segment_end_progress_km": 100}
    j = auth_client.post("/trips/search", json=body).json()
    assert j["agent_source"] == "deterministic" and j["agent_trace"] == [] and j["candidate_places"][0]["id"] == "demo-coffee"

def test_search_uses_agent_when_enabled(auth_client, monkeypatch):
    monkeypatch.setattr("backend.main._llm_search_enabled", lambda: True)
    monkeypatch.setattr("backend.main.run_route_agent", fake_agent_returning(["demo-coffee"]))
    j = auth_client.post("/trips/search", json={...}).json()
    assert j["agent_source"] == "agent" and j["agent_rationale"] and j["agent_trace"]

def test_agent_failure_falls_back_without_partial_results(auth_client, monkeypatch):   # Review Focus 1
    monkeypatch.setattr("backend.main._llm_search_enabled", lambda: True)
    monkeypatch.setattr("backend.main.run_route_agent", AsyncMock(return_value=None))
    j = auth_client.post("/trips/search", json={...}).json()
    assert j["agent_source"] == "deterministic" and j["agent_trace"] == []
```
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_search_endpoint.py -v`. Expected: FAIL with `KeyError: 'agent_source'`.
- [ ] **Step 3: Implement the endpoint.** Build `arrival` from `arrival_date` + `arrival_time` when both parse; otherwise `None`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Frontend request.** In `searchRoutePlaces`, send:
  - `arrival_time: currentStop?.time`;
  - `arrival_date: currentStop?.date`;
  - `current_stop_cost_sgd`: `estimated_cost_sgd` of `candidateForStop(currentStop)`, or `null`;
  - `remaining_budget_per_person_sgd`: `budgetPerPerson - costBreakdown.estimated_per_person_sgd`, or `null` if either value is missing.

  Store `result.agent_source`, `result.agent_rationale` and `result.agent_trace` in new state, and pass them through `assistant`.
- [ ] **Step 6: Frontend trace UI.** In `RouteAssistant`, when `agentSource === 'agent'`:
  - change the live pill text to `AGENT · GOOGLE PLACES`;
  - render the rationale as a line above the results;
  - render a `<details className="agent-trace"><summary>How the agent got here</summary><ol>` with one `<li>` per trace entry showing `{summary}`.

  Add the `.agent-trace` styles to `src/styles.css` to match `.request-results`.
- [ ] **Step 7: Verify the build.** Run `npm run build`. Expected: success. Then manually run a search with `OPENAI_API_KEY` set and check that the trace renders, and without it check that the UI is unchanged.
- [ ] **Step 8: Commit** with the message `Route place requests through the agent with a visible trace and deterministic fallback`.

### Task 11: OKF cache

**Files:**
- Modify: `backend/okf.py` (`OKFProfileExporter`)
- Test: `backend/tests/test_okf.py`

**Interfaces:**
- Produces: `OKFProfileExporter.export` is unchanged in signature. It caches per `owner_id` by `fingerprint(profile, trips, events) -> str`: the sha256 of the sorted-keys JSON of `profile`, `[(t["id"], t.get("updated_at")) for t in trips]` and `[e["id"] for e in events]`. A cache hit returns the cached dict and does not write the file.

- [ ] **Step 1: Write the failing tests.**
```python
def test_second_export_with_same_inputs_skips_write(tmp_path, monkeypatch):
    exporter = OKFProfileExporter()
    writes = []
    monkeypatch.setattr(Path, "write_text", lambda self, *a, **k: writes.append(self))
    exporter.export({"preferences": []}, owner_id="u1")
    exporter.export({"preferences": []}, owner_id="u1")
    assert len(writes) == 1

def test_new_event_invalidates_cache(monkeypatch):
    # second export with one extra event -> 2 writes and the new document mentions the event
    ...
```
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_okf.py -v`. Expected: FAIL (2 writes).
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** with the message `Cache the OKF profile until its inputs change`.

### Task 12: "What VibeTrip has learned about you" on the Profile page

**Files:**
- Modify: `backend/main.py` (`export_okf_profile` response), `src/App.jsx`, `src/components/ProfileView.jsx`, `src/styles.css`
- Test: `backend/tests/test_profile_endpoint.py`

**Interfaces:**
- Consumes: the `learned_signals` entries (Task 3) and the existing `recordAgentEvent(eventType, data)` in `App.jsx`.
- Produces: the `POST /profiles/okf` response adds `learned_signals: list` (additive). `ProfileView` gets new props `learnedSignals: list` and `onDismissSignal(signal: string)`.

- [ ] **Step 1: Write the failing test.**
```python
def test_profile_okf_returns_learned_signals(auth_client):
    j = auth_client.post("/profiles/okf", json={"preferences": ["local-gems"]}).json()
    assert {"signal": "local_food", "source": "profile"}.items() <= j["learned_signals"][0].items()

def test_dismiss_then_reload_hides_signal(auth_client):
    auth_client.post("/profiles/events", json={"event_type": "chatbot_search", "data": {"query": "quiet cafe"}})
    auth_client.post("/profiles/events", json={"event_type": "signal_dismissed", "data": {"signal": "quiet_low_crowd_stops"}})
    j = auth_client.post("/profiles/okf", json={"preferences": []}).json()
    assert all(s["signal"] != "quiet_low_crowd_stops" for s in j["learned_signals"])
```
  Note: `context_event_repository` is a module singleton. Have `auth_client` give each test a unique user id (e.g. `f"test-{uuid4()}"`) so events don't leak between tests.
- [ ] **Step 2: Run the tests and confirm they fail.** Run `.venv/bin/python -m pytest backend/tests/test_profile_endpoint.py -v`. Expected: FAIL with `KeyError: 'learned_signals'`.
- [ ] **Step 3: Implement the backend field.** Then run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 4: Frontend.** When `activeNav === 'Travel profile'`, `POST /profiles/okf` with the current profile preferences and adventure level, and store `learned_signals`. `onDismissSignal` awaits `recordAgentEvent('signal_dismissed', { signal })` and then reloads. In `ProfileView`, add a `profile-card` section titled "What VibeTrip has learned about you", with one row per signal:
  - the label;
  - a source chip: "From your profile", "Learned from your trips" or "Profile + trips";
  - `evidence_count` shown as "based on N actions" when greater than 0;
  - a "Not me" button only when the source is not `profile`.

  The empty state reads "Nothing learned yet. Plan a few trips and swap some stops."
- [ ] **Step 5: Verify the build.** Run `npm run build`. Expected: success.
- [ ] **Step 6: Commit** with the message `Show learned travel signals on the profile page with a way to dismiss them`.

### Task 13: LangSmith env, README rewrite, final verification

**Files:**
- Modify: `.env.example`, `README.md`

- [ ] **Step 1: Update `.env.example`.** Append a commented block:
  ```
  # Optional LangSmith tracing (off by default). Sends prompts, including the OKF profile, to LangSmith.
  LANGSMITH_TRACING=false
  LANGSMITH_API_KEY=
  LANGSMITH_PROJECT=vibetrip
  # VIBETRIP_ROUTE_AGENT_ENABLED=true
  # VIBETRIP_AGENT_TIMEOUT_SECONDS=20
  ```
- [ ] **Step 2: Rewrite the README "Product / agent direction" section.**
  - The planner is a LangGraph workflow with two bounded agentic parts: the route assistant agent (tools, caps, validation, fallback) and the repair loop (skips optional stops, never changes route mode, keeps the best attempt).
  - Update the graph diagram to show the `repair` loop.
  - Document the new response fields (`repair_log`, `agent_source`, `agent_rationale`, `agent_trace`, `learned_signals`).
  - Document how to run the tests, LangSmith, and the new env vars.
  - Remove "No automated test suite" and every claim the code doesn't back, e.g. calling each node an "agent".
- [ ] **Step 3: Run the full verification.**
  ```bash
  .venv/bin/python -m pytest -q && .venv/bin/python -m compileall -q backend && npm run build && git diff --check
  ```
  Expected: all pass, with no output from `git diff --check`.
- [ ] **Step 4: Manual checklist.** Run the README checklist twice: first with no keys, then with `OPENAI_API_KEY` set (Google optional). Confirm:
  - a late trip shows a repair note;
  - the route assistant shows the agent trace;
  - the Profile page lists signals and "Not me" removes one.
- [ ] **Step 5: Check the bug journal.** Read the Prevention lines in `~/.claude/bug-journal/` (the VibeTrip file and `general.md`), and confirm the changes don't reintroduce a logged mistake: waypoint ordering, Explore checkpoint reuse, the Fastest fuel stop, map markers, request limits.
- [ ] **Step 6: Commit** with the message `Document the agentic planner, tests, and optional LangSmith tracing`.
