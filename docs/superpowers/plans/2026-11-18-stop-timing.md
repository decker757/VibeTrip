# Stop Timing Implementation Plan

> Executed inline (superpowers:executing-plans), TDD per task.

**Goal:** Choose fuel and meal stops by where on the route you'd need them, and backfill search per empty sample point.
**Spec:** `docs/superpowers/specs/2026-11-18-stop-timing-design.md`

## Global constraints
- Constants live in `backend/graph.py`:
  - `FUEL_MIN_GAP_KM = 150`
  - `TARGET_WINDOW_RATIO = 0.15`
  - `LUNCH_TARGET = time(12, 30)`
  - `MEAL_TARGET_BOUNDS = (0.2, 0.8)`
- `day_builder` goldens (demo data, one candidate per kind) must stay unchanged.
- The full suite must pass.

## Review focus
- The LLM-ranked meal pick is kept when it falls inside the window.
- A start after 12:30 aims the meal at the 50% mark.
- Fastest mode's fallback through every fuel option still works.
- A route with no progress data on any candidate behaves as it does today.

### Task 1: Target-ordered stop options (`backend/graph.py`, test `backend/tests/test_day_builder.py`)
- Produces:
  - `_order_near_target(options: list[dict], target_km: float, window_km: float) -> list[dict]`
    - Candidates inside the window come first, in input order.
    - The rest follow, sorted by distance to the target.
    - Candidates with no progress come last.
  - `_fuel_targets(distance_km, drive_minutes) -> list[float]`
  - `_meal_target_km(state, distance_km, drive_minutes) -> float`
- Change `_pick_stop_options`:
  - `fuel_stops`, the practical fallback and `meal_options` are ordered by their targets.
  - `additional_fuel_stop` is the best candidate near the second target that is at
    least `FUEL_MIN_GAP_KM` from `fuel_stop`.
- Tests:
  - `test_order_near_target_keeps_rank_inside_window`
  - `test_second_fuel_is_spaced_from_first`
  - `test_no_second_fuel_when_none_is_far_enough`
  - `test_meal_targets_lunch_time`
  - `test_meal_targets_midpoint_when_drive_misses_lunch`
  - The goldens still pass.

### Task 2: Per-point backfill (`backend/providers.py`, test `backend/tests/test_providers.py`)
- Track fuel and food found per corridor sample point. Run the 15 km pass only for the
  points and types that are missing.
- Tests:
  - `test_backfill_runs_only_for_points_missing_fuel_or_food`
  - The existing skip test still passes.

### Task 3: Live check, then deploy on Ernest's go
- Compare before and after on Arizona → Las Vegas and LA → Santa Barbara.
- Run the full suite.
- Merge, push, `railway up`.
