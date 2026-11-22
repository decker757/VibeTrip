"""Replace the Explore feed's sample trips with real planner output.

Runs every trip in src/app/exploreTrips.json through the same /trips/plan code
the app uses (in-process, live Google provider) and writes the route, timed
itinerary, candidate places and costs back into that file.

    .venv/bin/python scripts/seed_explore_trips.py            # all trips
    .venv/bin/python scripts/seed_explore_trips.py <trip-id>  # one trip

Needs GOOGLE_MAPS_API_KEY and VIBETRIP_LIVE_MAPS_ENABLED=true in .env. A trip
that falls back to the demo provider is never saved: the script waits out the
per-minute Google budget and retries instead.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TRIPS_FILE = ROOT / "src" / "app" / "exploreTrips.json"
START_TIME = "09:00"
BUDGET_WAIT_SECONDS = 65
MAX_ATTEMPTS = 3

load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.auth import get_current_user  # noqa: E402
from backend.main import app  # noqa: E402

SEED_USER = {"id": "explore-seed", "email": "seed@vibetrip.local", "name": "Explore seed"}


def next_saturday(today: date) -> date:
    return today + timedelta(days=(5 - today.weekday()) % 7 or 7)


def plan_request(trip: dict, start_date: str) -> dict:
    return {
        "start": trip["start"],
        "destination": trip["destination"],
        "travellers": trip["travellers"],
        "budget_per_person": trip["budget_per_person"],
        "start_date": start_date,
        "end_date": start_date,
        "start_time": START_TIME,
        "preferences": trip.get("preferences", []),
        "adventure_level": trip["adventure_level"],
        "route_mode": trip["route_mode"],
    }


def problem_with(result: dict) -> str | None:
    """Why this result must not be saved as a real snapshot, if anything."""
    if result.get("provider") != "google":
        return f"provider was {result.get('provider')!r}: {result.get('warning')}"
    if not result.get("route", {}).get("polyline"):
        return "route has no polyline"
    if not any(item.get("place_id") for item in result.get("itinerary", [])):
        return "itinerary has no real places"
    return None


def snapshot(trip: dict, result: dict, start_date: str) -> dict:
    """Keep only the places the itinerary uses: "Use this route" re-plans live
    around them, so the rest of the candidate list would just be stale weight."""
    route = result["route"]
    itinerary_ids = {item.get("place_id") for item in result["itinerary"] if item.get("place_id")}
    return {
        **trip,
        "start_date": start_date,
        "start_time": START_TIME,
        "end_date": route.get("estimated_arrival_date") or start_date,
        "route": route,
        "itinerary": result["itinerary"],
        "candidate_places": [place for place in result["candidate_places"] if place.get("id") in itinerary_ids],
        "cost_breakdown": result["cost_breakdown"],
        "recommendation_source": result.get("recommendation_source", "deterministic"),
        "seeded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def seed(client: TestClient, trip: dict, start_date: str) -> dict | None:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.post("/trips/plan", json=plan_request(trip, start_date))
        if response.status_code != 200:
            problem = f"HTTP {response.status_code}: {response.text[:200]}"
        else:
            result = response.json()
            problem = problem_with(result)
            if not problem:
                return snapshot(trip, result, start_date)
        print(f"  attempt {attempt}: {problem}")
        if attempt < MAX_ATTEMPTS:
            print(f"  waiting {BUDGET_WAIT_SECONDS}s for the Google request budget to reset")
            time.sleep(BUDGET_WAIT_SECONDS)
    return None


def main(only_ids: list[str]) -> int:
    trips = json.loads(TRIPS_FILE.read_text())
    start_date = next_saturday(date.today()).isoformat()
    app.dependency_overrides[get_current_user] = lambda: SEED_USER
    failed = []
    with TestClient(app) as client:
        for index, trip in enumerate(trips):
            if only_ids and trip["id"] not in only_ids:
                continue
            print(f"{trip['start']} → {trip['destination']} ({trip['route_mode']})", flush=True)
            seeded = seed(client, trip, start_date)
            if not seeded:
                failed.append(trip["id"])
                continue
            trips[index] = seeded
            stops = ", ".join(f"{item['time']} {item['title']}" for item in seeded["itinerary"])
            print(f"  {seeded['route']['distance_km']} km, {seeded['route']['drive_minutes']} min · {stops}", flush=True)
            # Save as we go so a later failure keeps the trips already seeded.
            TRIPS_FILE.write_text(json.dumps(trips, indent=2, ensure_ascii=False) + "\n")
    if failed:
        print(f"Not seeded (kept as before): {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
