# Stop timing: fuel and lunch when you need them

Date 2026-11-18. Branch `fix/stop-timing`. Approved by Ernest in conversation.

## Why
The planner picks the fuel stop by smallest detour and the meal by rank. Neither choice
looks at when in the day you'd reach the stop. Two results on Arizona → Las Vegas:
- two fuel stops 0.1 km apart;
- lunch at 15:15, with the first stop six hours into the drive.

An interviewer typing their own route should get a day that reads like a real road trip.

## Goals
- **Fuel targets.** One fuel stop aims at 50% of the route. Drives of 6 h or more aim
  at 1/3 and 2/3. The second fuel stop must be at least 150 km past the first; if no
  station qualifies, there is no second fuel stop.
- **Meal target.** Aim at the route km reached at 12:30, estimated from the start time
  and average speed (distance ÷ drive minutes). Clamp it to 20–80% of the route. If
  the drive doesn't span 12:30, aim at 50%.
- **Selection.** Pick the best-ranked candidate within ±15% of route length of the
  target. If none is in that window, pick the candidate nearest the target. Places
  without route progress come last.
- **Search backfill per point.** Any corridor sample point whose broad search returned
  no fuel (or no food) gets the 15 km single-type pass for that type. Today the pass
  only runs when the whole route has none.

## Non-goals
- Coffee and attraction choice stay as they are.
- No daily driving cap or forced-break rule.
- No change to route geometry, the repair loop or make-room.

## Anti-goals
- Breaking the demo routes. LA → Santa Barbara must still plan.
- Extra Google requests on dense routes, where every point already has fuel and food.

## Approaches
- **Chosen: a target plus a ranked window.** Respects existing ranking, including the
  LLM's pick, near the target.
- **Rejected: a minimum gap between fuel stops only.** Fixes the duplicate, but not
  late lunches or long first legs.
