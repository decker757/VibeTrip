"""Bounded repair loop for plans that arrive later than the user's end time.

The LLM may only choose which optional stop kind to skip (or to accept the
warning). Code applies the skip, rebuilds the day, and re-validates. The route
mode is never changed, ``meal`` and the only fuel stop are never skipped, and a
plan gets at most ``MAX_REPAIR_ATTEMPTS`` skips across the graph and the
post-reroute check. In make-room mode (the traveller chose a destination
activity) the cap is ``MAX_MAKE_ROOM_ATTEMPTS`` and accept_warning is not offered.

This module must not import ``graph.py`` (the graph imports it); callers pass
the day builder in as ``rebuild``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

from .recommender import get_chat_model, llm_enabled

RepairAction = Literal["skip_coffee", "skip_attraction", "skip_extra_fuel", "accept_warning"]


class RepairDecision(BaseModel):
    """The only fields the LLM is allowed to return."""

    action: RepairAction
    reason: str


MAX_REPAIR_ATTEMPTS = 2
# Make-room mode: the traveller chose a destination activity, so every optional kind may go.
MAX_MAKE_ROOM_ATTEMPTS = 3
UNFIXABLE_REASON = "Unfixable without changing route mode"
MODE_SUGGESTION = "Start earlier, allow a later end time, or try Fastest."
# Rule order when no LLM answer is usable: cheapest experience loss first.
RULE_ORDER: list[RepairAction] = ["skip_coffee", "skip_extra_fuel", "skip_attraction"]
SKIP_KINDS: dict[RepairAction, str] = {"skip_coffee": "coffee", "skip_attraction": "attraction", "skip_extra_fuel": "extra_fuel"}


def _late_warning(state: dict[str, Any]) -> dict[str, str] | None:
    return next((w for w in (state.get("route") or {}).get("warnings", []) if w.get("code") == "late_arrival"), None)


def available_actions(state: dict[str, Any]) -> list[RepairAction]:
    """One skip action per optional kind in the itinerary, plus accept_warning."""
    kinds = [item.get("kind") for item in state.get("itinerary", [])]
    present = {"skip_coffee": "coffee" in kinds, "skip_attraction": "attraction" in kinds, "skip_extra_fuel": kinds.count("fuel") > 1}
    actions: list[RepairAction] = [action for action in ("skip_coffee", "skip_attraction", "skip_extra_fuel") if present[action]]
    return [*actions, "accept_warning"]


def _skip_actions(state: dict[str, Any]) -> list[RepairAction]:
    return [action for action in available_actions(state) if action != "accept_warning"]


def _attempt_cap(state: dict[str, Any]) -> int:
    return MAX_MAKE_ROOM_ATTEMPTS if state.get("make_room_mode") else MAX_REPAIR_ATTEMPTS


def should_repair(state: dict[str, Any]) -> Literal["repair", "finalize"]:
    if (
        _late_warning(state)
        and int(state.get("repair_attempts") or 0) < _attempt_cap(state)
        and not state.get("repair_settled")
        and _skip_actions(state)
    ):
        return "repair"
    return "finalize"


def _with_mode_suggestion(route: dict[str, Any], route_mode: str) -> dict[str, Any]:
    """Append the route-mode hint to a late schedule warning, at most once."""
    warning = route.get("schedule_warning")
    if route_mode == "fastest" or not warning or warning.endswith(MODE_SUGGESTION):
        return route
    return {**route, "schedule_warning": f"{warning} {MODE_SUGGESTION}"}


def _log_entry(state: dict[str, Any], warning: dict[str, str], action: RepairAction, reason: str, source: str) -> list[dict[str, Any]]:
    entry = {"attempt": int(state.get("repair_attempts") or 0) + 1, "warning": warning["message"], "action": action, "reason": reason, "source": source}
    return [*state.get("repair_log", []), entry]


def _llm_decision(state: dict[str, Any], warning: dict[str, str], actions: list[RepairAction]) -> RepairDecision | None:
    """Ask the LLM for one action; None when disabled, failed, or not on offer."""
    if not llm_enabled():
        return None
    prompt = {
        "warning": warning["message"],
        "route_mode": state.get("route_mode", "balanced"),
        "itinerary": [{"time": item.get("time"), "kind": item.get("kind"), "title": item.get("title"), "duration_min": item.get("duration_min")} for item in state.get("itinerary", [])],
        "learned_preferences": state.get("learned_preferences", []),
        "adventure_level": state.get("adventure_level", 50),
        "allowed_actions": actions,
    }
    try:
        decision = get_chat_model().with_structured_output(RepairDecision).invoke([
            (
                "system",
                "You are VibeTrip's schedule repairer. The trip arrives later than the traveller wants. "
                "Choose exactly one action from allowed_actions: skip one optional stop kind, or accept_warning "
                "to keep every stop. You cannot change the route mode. Use the traveller's adventure level and "
                "learned preferences: an adventurous traveller keeps a scenic stop and drops coffee first. "
                "Give a one-sentence reason addressed to the traveller.",
            ),
            ("human", json.dumps(prompt, ensure_ascii=False)),
        ])
    except Exception:
        # A failed model call must never block the deterministic repair.
        return None
    # Structured-output parsers can return None; anything but an on-offer RepairDecision means no LLM choice.
    return decision if isinstance(decision, RepairDecision) and decision.action in actions else None


def repair_step(state: dict[str, Any], rebuild: Callable[[dict], dict]) -> dict[str, Any]:
    """Decide one repair; the caller rebuilds the day afterwards."""
    warning = _late_warning(state) or {"code": "late_arrival", "message": ""}
    skips = _skip_actions(state)
    skipped = list(state.get("skipped_stop_kinds", []))
    # Feasibility check: if skipping every optional kind is still late, keep the stops.
    everything_skipped = [*skipped, *(SKIP_KINDS[action] for action in skips)]
    if _late_warning(rebuild({**state, "skipped_stop_kinds": everything_skipped})):
        return {
            **state,
            "repair_settled": True,
            "repair_unfixable": True,
            "route": _with_mode_suggestion(state.get("route") or {}, state.get("route_mode", "balanced")),
            "repair_log": _log_entry(state, warning, "accept_warning", UNFIXABLE_REASON, "rule"),
        }

    # In make-room mode the chosen activity outranks optional stops, so keeping them is not on offer.
    offered: list[RepairAction] = skips if state.get("make_room_mode") else [*skips, "accept_warning"]
    decision = _llm_decision(state, warning, offered)
    if decision is None:
        action = next(action for action in RULE_ORDER if action in skips)
        decision, source = RepairDecision(action=action, reason=f"Skipped the {SKIP_KINDS[action].replace('_', ' ')} stop to arrive by {state.get('end_time', '18:00')}."), "rule"
    else:
        source = "llm"
    repair_log = _log_entry(state, warning, decision.action, decision.reason, source)
    if decision.action == "accept_warning":
        return {**state, "repair_settled": True, "repair_log": repair_log}
    return {
        **state,
        "skipped_stop_kinds": [*skipped, SKIP_KINDS[decision.action]],
        "repair_attempts": int(state.get("repair_attempts") or 0) + 1,
        "repair_snapshots": [*state.get("repair_snapshots", []), _snapshot(state)],
        "repair_log": repair_log,
    }


def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
    # skipped_stop_kinds travels with the snapshot so a restored plan stays
    # consistent when main.py rebuilds it after a reroute.
    return {"itinerary": state.get("itinerary", []), "route": state.get("route") or {}, "skipped_stop_kinds": list(state.get("skipped_stop_kinds", []))}


def _score(version: dict[str, Any]) -> tuple[int, int]:
    route = version.get("route") or {}
    return len(route.get("warnings", [])), int(route.get("arrival_offset_minutes") or 0)


def finalize_best(state: dict[str, Any]) -> dict[str, Any]:
    """Keep the best attempt by (warning count, arrival offset).

    Snapshots come first so a tie keeps the version with more stops. Snapshots
    are consumed here, so a later repair run never restores a stale route.
    """
    best = min([*state.get("repair_snapshots", []), _snapshot(state)], key=_score)
    route = best["route"]
    if state.get("repair_unfixable") and _late_warning(best):
        # day_builder rewrites schedule_warning on every rebuild, so re-apply the hint.
        route = _with_mode_suggestion(route, state.get("route_mode", "balanced"))
    return {**state, **best, "route": route, "repair_snapshots": [], "repair_log": state.get("repair_log", [])}


def repair_until_settled(state: dict[str, Any], rebuild: Callable[[dict], dict]) -> dict[str, Any]:
    """Run the same bounded loop outside the graph (used after a reroute)."""
    while should_repair(state) == "repair":
        state = rebuild(repair_step(state, rebuild))
    return finalize_best(state)
