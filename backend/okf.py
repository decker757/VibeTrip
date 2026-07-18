"""Private Open Knowledge Format (OKF) profile exporter.

The database/profile payload remains the source of truth. This adapter creates
an agent-readable Markdown document with YAML frontmatter and stores it outside
the repository so it can later be replaced by an object-store or knowledge
catalog writer without changing the planner contract.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .user_context import build_user_context


OKF_ROOT = Path(os.getenv("VIBETRIP_OKF_DIR", Path(__file__).with_name("okf_profiles")))
OKF_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_owner_id(owner_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", owner_id)[:80] or "demo-user"


def _yaml_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _profile_tags(profile: dict[str, Any]) -> list[str]:
    tags = {"exchange-student"}
    tags.update(str(item) for item in profile.get("preferences", []) if item)
    adventure_level = int(profile.get("adventure_level") or 50)
    tags.add("adventurous" if adventure_level >= 70 else "laid-back" if adventure_level <= 35 else "balanced-pace")
    return sorted(tags)


def render_profile_okf(context: dict[str, Any], owner_id: str = "demo-user", timestamp: str | None = None) -> str:
    """Render a private, versioned user-context document in OKF's shape."""
    profile = context.get("profile", {})
    name = profile.get("name") or "VibeTrip traveller"
    home_base = profile.get("home_base") or "Singapore"
    adventure_level = int(profile.get("adventure_level") or 50)
    preferences = [str(item) for item in profile.get("preferences", []) if item]
    timestamp = timestamp or datetime.now(timezone.utc).isoformat()
    preference_lines = "\n".join(f"- {item}" for item in preferences) or "- No explicit preference selected"
    pace = profile.get("pace") or ("adventurous" if adventure_level >= 70 else "laid-back" if adventure_level <= 35 else "balanced")
    history_lines = "\n".join(
        f"- {item.get('start')} → {item.get('destination')} · {item.get('route_mode')} · {len(item.get('stops') or [])} stops"
        for item in context.get("trip_history", [])
    ) or "- No saved trip history yet"
    signal_lines = "\n".join(
        f"- {item.get('signal')} (confidence {item.get('confidence', 0):.2f}; evidence {item.get('evidence_count', 0)})"
        for item in context.get("learned_signals", [])
    ) or "- No learned signals yet"
    feedback_lines = "\n".join(
        f"- {item.get('event_type')}: {item.get('reason') or item.get('query') or item.get('new_place') or 'recorded preference'}"
        for item in context.get("feedback_events", [])[-10:]
    ) or "- No explicit route feedback yet"
    return f"""---
type: vibetrip.user_context
schema_version: {_yaml_string(context.get('schema_version', '0.2'))}
title: {_yaml_string(name)}
description: {_yaml_string('Private, derived travel context for an exchange-student road-trip planner')}
resource: {_yaml_string(f'vibetrip://profiles/{owner_id}')}
tags: {json.dumps(_profile_tags(profile), ensure_ascii=False)}
timestamp: {_yaml_string(timestamp)}
---

# Traveller context

- Home base: {home_base}
- Exchange student: {'yes' if profile.get('exchange_student', True) else 'no'}
- Pace: {pace}
- Adventure level: {adventure_level}/100
- Budget: SGD {int(profile.get('budget_per_person_sgd') or 0)} per person
- Crowd tolerance: {profile.get('crowd_tolerance') or 'medium'}

# Explicit preferences

{preference_lines}

# Trip history

{history_lines}

# Learned signals

{signal_lines}

# Recent feedback

{feedback_lines}

# Agent constraints

- Prefer feasible places within the active route segment.
- Verify opening hours against the estimated local arrival time.
- Keep fuel, food, tolls, tickets, and buffer time within the stated budget and schedule.
- Treat this document as preference context; hard routing and safety constraints remain deterministic.
"""


class OKFProfileExporter:
    """Write and return a private OKF profile artifact for agent consumption."""

    def export(
        self,
        profile: dict[str, Any],
        owner_id: str = "demo-user",
        trips: list[dict[str, Any]] | None = None,
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        safe_owner_id = _safe_owner_id(owner_id)
        context = build_user_context(profile, trips=trips, events=events)
        document = render_profile_okf(context, owner_id=safe_owner_id)
        destination = OKF_ROOT / safe_owner_id / "profile.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document, encoding="utf-8")
        return {
            "format": "okf",
            "resource": f"vibetrip://profiles/{safe_owner_id}",
            "path": str(destination),
            "document": document,
            "context": context,
        }


okf_profile_exporter = OKFProfileExporter()
