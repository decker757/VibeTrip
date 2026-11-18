# Make room for the destination: time-budget planning

Date: 2026-11-18. Branch: `feature/make-room-time-budget`, in the worktree at `../VibeTrip-make-room`.

## Intent

Today the late-arrival repair trims optional stops to meet a fixed 18:00 cutoff. The user never sees that cutoff and can't change it: the "Latest arrival" input is hidden by CSS and the time defaults to `18:00`. Ernest's point is that travellers don't know their end time up front, so asking for one is the wrong model. The real deadline comes from what they want to do at the destination.

The new feature works like this. When the user picks a place in "Make room for the destination", the planner takes the deadline from that place's opening hours. It replans the drive against that deadline. If the drive runs late, it trims optional stops. If there is spare time, the route agent fills it with a stop along the existing route.

Why this matters. It makes the agent's job honest: deciding how to spend a time budget, not deleting stops to hit a made-up number. It also gives the interview on 2026-11-19 a story about critiquing and improving the design. The "one agent, two ways in" framing comes from this: the user can ask the agent directly ("Ask for a better fit"), or the planner can call it when there is time to spend.

## Goals

- Clicking **Add to route** on a destination suggestion replans the trip with `end_time` set to a deadline derived from that place.
- When the replanned trip runs late, the existing repair loop trims optional stops against the real deadline. If even trimming can't make it fit, the destination is not added and the user is told why.
- When spare time is at least 45 minutes, the route agent runs in a new **fill mode**. It searches the longest gap between stops for something that fits the spare time and the user's learned preferences, and the result is returned as a suggestion.
- The panel shows the outcome: the deadline, the arrival time and the spare time, plus the agent's suggestion with its rationale and its "How the agent got here" trace. The user adds the suggestion with one click.

## Non-goals

- Deadlines for trips that arrive on a later day. If the replanned arrival is not on the start date, don't apply a deadline: add the destination the way it's added today and show a note.
- Saving the chosen activity or deadline with saved trips.
- Any change to the initial **Make my route** flow, which keeps the 18:00 default and its current behaviour.
- Removing the hidden "Latest arrival" input, deriving deadlines from sunset, or adding a daily driving-hours cap.
- More than one fill suggestion, or filling more than one gap.

## Anti-goals (the feature fails if any of these happen, even if it technically works)

- The live demo on `main` breaks. All work stays on the branch, and nothing is deployed unless Ernest says so.
- The agent adds stops without the user clicking. It only suggests.
- A plain **Make my route** gets slower or makes extra LLM calls. Fill mode runs only after a destination is added.
- The agent suggests a place it didn't find through a tool, a place closed at arrival, or one that doesn't fit the spare time. Code enforces all three rules, the same way the route agent already does.

## Constraints

- Reuse what exists: `repair.py` for the trim loop, `route_agent.py` for its tools, its validation and its step and search caps, `opening_hours.py` for opening hours, and the `/trips/plan` endpoint, which already reroutes and runs the repair loop.
- The LLM may be off or may fail. When it does, fall back deterministically: take the best-scoring along-route candidate from the plan's `candidate_places` that sits inside the gap and fits the spare time. Label it as not coming from the agent, the same way `/trips/search` labels its deterministic results.
- Fill mode uses the same LLM rate-limit slot as other agent searches (`reserve_llm_search_slot`) and the same timeout.
- The backend test suite has 90 passing tests. Every existing test still passes and the new behaviour gets tests.

## Approaches considered

- **A. Frontend does the time maths and the existing agent runs unchanged.** This is the smallest change, but it duplicates the backend's scheduling logic in the browser. It also can't trim stops, and the agent never learns the time limit. Rejected.
- **B. Replan with a real deadline, then the agent fills the spare time.** This is the chosen approach. It reuses the repair loop and the route agent, and all the time maths stays in the backend. The cost: replanning resets manual stop edits, and the endpoint gets slower when a destination is added, by the plan time plus up to about 20 s for the agent.
- **C. A new agent owns the whole time budget,** with add-stop, remove-stop and check-schedule tools. This is the most agentic option, but it's too much new surface and too risky to finish the night before the interview. Rejected.

## Design (decided)

**Request.** `TripRequest` gets an optional `destination_activity` field holding the place dict as the frontend received it: `id`, `name`, `category` and `opening_hours`. When the field is present:

1. **Deadline.** Visit time is 60 min for food (restaurant, cafe, food court) and 90 min for everything else. Take the place's opening periods on the start date (`opening_hours.periods`, matched to the start date's weekday):
   - A closing time after midnight is capped at 23:59 that day.
   - With split hours (for example 11:00–14:00 and 17:00–22:00), use the **first** period where `close − visit` is no earlier than the trip's current arrival. That's the earliest window you can still make. The frontend sends that current arrival as `current_arrival_time`.
   - If no period that day can be made at the current arrival, use the **last** period that day. Trimming may still make it fit; if it doesn't, the outcome is `wont_fit`.
   - The deadline is that period's `close − visit`, and it becomes `end_time`.
   - If arrival falls before the window opens, the wait is simply counted as spare time.
   - Status `no_hours` (no deadline; the place is added the way it is today, with a note) covers two cases: no periods on that date, or a period with no `close` (open 24 hours).
2. **Replan.** Run the existing `/trips/plan` path with that `end_time`. The repair loop runs in a new **make-room mode**:
   - all three optional kinds (coffee, extra fuel, attraction) can be skipped, so the cap is 3 attempts instead of 2;
   - `accept_warning` is not offered to the LLM, because the user explicitly chose this activity, so the planner must not keep optional stops at its expense.
   
   Make-room mode is a parameter that defaults to off, so the existing repair behaviour and its tests don't change. The existing feasibility check still writes the "Unfixable" entry when even skipping everything is late.
3. **Outcome.** Compare the final arrival against the deadline:
   - `wont_fit`: the arrival is still after the deadline, even after trimming as far as possible.
   - `fits`: the arrival is on time, with a spare time of `deadline − arrival` in minutes.
   
   **Multi-day trips never reach the backend in make-room mode.** If the current trip's `estimated_arrival_date` is later than the start date, the frontend uses today's add-and-reroute path and shows a note ("deadlines apply to same-day arrivals only"). This avoids trimming against a same-day deadline that doesn't apply.
   
   "Arrival" here means the planner's arrival in the destination city (check-in time). It doesn't include the short drive from there to the activity. This stand-in is acceptable because destination suggestions are, by construction, near the destination.
4. **Fill.** If the status is `fits` and spare time is at least 45 min, run the route agent in fill mode:
   - **Segment:** the longest gap between consecutive itinerary stops by `route_progress_km`, including the start (0 km) and the destination (`distance_km`) as endpoints.
   - **Query:** generated in code from learned signals, then route mode. `scenic_views` → "scenic viewpoint or nature stop", `local_food` → "local food spot", `quiet_low_crowd_stops` → "quiet low-crowd stop", otherwise "worthwhile stop". The agent may rephrase the query in its own searches.
   - **Prompt:** a fill-specific system prompt that says "add one stop that fits N spare minutes" instead of "replace one stop". The tools are the same.
   - **Code-enforced fit:** a candidate is kept only if `detour_minutes + stop_minutes ≤ spare_minutes`, where stop time is 30 min. `detour_minutes` is already the full out-and-back time (`providers.py`), so it is not doubled. This check runs alongside the existing "seen by a tool" and "open at arrival" checks.
   - **Fallback:** if the agent fails or returns nothing valid, use the deterministic choice described under Constraints.

**Response.** `/trips/plan` adds a `make_room` object, present only when `destination_activity` was sent:
`{status, destination_place_id, deadline, arrival, spare_minutes, suggestion}`.
`suggestion` is either `null` or `{candidates, rationale, trace, source: "agent" | "deterministic"}`.
Every other response field keeps its current shape.

**Frontend.**
- **Add to route** on a destination suggestion sends the place as `destination_activity` to `/trips/plan`. The button shows a loading state.
  - The response is applied only after it comes back, so `generateTrip`'s fetch is separated from the step that applies the result.
  - On `wont_fit`, **keep the previous trip unchanged**: don't add the place. Show the plain message: "You'd arrive HH:MM, after <place> closes at HH:MM. Start earlier or pick another place."
  - On `fits` or `no_hours`, apply the replanned trip, then insert the destination before check-in and reroute, the way `addDestinationCandidate` does today.
  - As with today's insert, `/trips/reroute` only recomputes the map line, so the timeline times after the insertion are the client-side estimate. That's an accepted limitation for this change.
- The panel shows a status line, for example: "✓ The Broad added · closes 17:00 · plan to arrive by 15:30 · you arrive 13:40, 1h50 to spare". When `suggestion` is present, it also shows a suggestion card with the place, the rationale, an **Add to route** button that inserts the place at its route position and reroutes, and a collapsible "How the agent got here".
- When the user has manually edited stops, adding a destination replans and discards those edits. The UI says so before it happens.

## Left to the builder

- Exactly where the deadline and gap helpers live (`opening_hours.py`, a new `make_room.py`, or `main.py`) and their names.
- How fill mode plugs into `route_agent.py`: a `mode` field on `RouteAgentContext`, or a separate entry function. Either is fine as long as the existing replace-mode behaviour and its tests don't change.
- How the frontend inserts a suggestion at its route position.
- Exact UI copy and styling, as long as it matches the existing panel's style.
- Test structure, using the existing fakes in `backend/tests/fakes.py`.
