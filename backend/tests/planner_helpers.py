"""Shared builders for planner tests (used by conftest and the golden generator)."""

import asyncio

from backend.graph import day_builder, detour_reviewer, vibe_matcher
from backend.providers import DemoMapsProvider


def build_demo_state(route_mode: str = "balanced", end_time: str = "18:00") -> dict:
    result = asyncio.run(DemoMapsProvider().plan_trip("A", "B", 400, "medium", "08:10", route_mode))
    return {
        "start": "A",
        "destination": "B",
        "budget_per_person": 400,
        "start_date": "2026-11-20",
        "start_time": "08:10",
        "end_time": end_time,
        "adventure_level": 70,
        "route_mode": route_mode,
        "route": result.route,
        "candidate_places": result.candidates,
    }


def run_deterministic_planner(state: dict) -> dict:
    """vibe_matcher -> detour_reviewer -> day_builder, skipping provider and LLM nodes."""
    return day_builder(detour_reviewer(vibe_matcher(state)))
