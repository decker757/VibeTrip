"""Small persistence boundary for saved trips and the Explore feed.

The MVP keeps the repository deliberately boring: Postgres is used when a
working DATABASE_URL and psycopg installation are available, otherwise the
same contract falls back to process memory so local frontend work does not
require a running database.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


OWNER_ID = "demo-user"


EXPLORE_SEED_TRIPS: list[dict[str, Any]] = [
    {
        "id": "seed-boston-new-york-scenic",
        "owner_id": "seed-maya",
        "author_name": "Maya · NUS exchange",
        "title": "Coastline, coffee, and a little history",
        "start": "Boston, MA",
        "destination": "New York, NY",
        "route_mode": "scenic",
        "adventure_level": 78,
        "budget_per_person": 180,
        "travellers": 3,
        "start_date": "2026-06-13",
        "end_date": "2026-06-13",
        "start_time": "08:00",
        "end_time": "20:00",
        "preferences": ["local-gems", "adventurous", "student-budget"],
        "route": {"distance_km": 365, "drive_minutes": 244, "estimated_arrival_time": "19:15", "route_mode": "scenic"},
        "itinerary": [
            {"time": "09:20", "title": "Cedar Street Café", "kind": "coffee", "duration_min": 25},
            {"time": "11:40", "title": "Mystic Seaport", "kind": "attraction", "duration_min": 60},
            {"time": "14:10", "title": "Shell + bathroom", "kind": "fuel", "duration_min": 15},
            {"time": "16:00", "title": "Dinner in Brooklyn", "kind": "meal", "duration_min": 55},
        ],
        "candidate_places": [],
        "cost_breakdown": {"estimated_total_sgd": 180, "estimated_per_person_sgd": 60, "items": []},
        "is_public": True,
        "created_at": "2026-06-14T08:00:00+00:00",
    },
    {
        "id": "seed-portland-seattle-balanced",
        "owner_id": "seed-daniel",
        "author_name": "Daniel · NTU exchange",
        "title": "Rainy-day stops up the Pacific Northwest",
        "start": "Portland, OR",
        "destination": "Seattle, WA",
        "route_mode": "balanced",
        "adventure_level": 56,
        "budget_per_person": 145,
        "travellers": 4,
        "start_date": "2026-05-09",
        "end_date": "2026-05-09",
        "start_time": "09:00",
        "end_time": "18:00",
        "preferences": ["slow-mornings", "student-budget"],
        "route": {"distance_km": 280, "drive_minutes": 175, "estimated_arrival_time": "16:50", "route_mode": "balanced"},
        "itinerary": [
            {"time": "10:10", "title": "Farmers market coffee", "kind": "coffee", "duration_min": 25},
            {"time": "12:35", "title": "Centralia lunch", "kind": "meal", "duration_min": 50},
            {"time": "15:15", "title": "Fuel + convenience", "kind": "fuel", "duration_min": 15},
        ],
        "candidate_places": [],
        "cost_breakdown": {"estimated_total_sgd": 145, "estimated_per_person_sgd": 36, "items": []},
        "is_public": True,
        "created_at": "2026-05-10T08:00:00+00:00",
    },
    {
        "id": "seed-munich-prague-fastest",
        "owner_id": "seed-isha",
        "author_name": "Isha · SMU exchange",
        "title": "Munich to Prague with only the good breaks",
        "start": "Munich, Germany",
        "destination": "Prague, Czechia",
        "route_mode": "fastest",
        "adventure_level": 34,
        "budget_per_person": 120,
        "travellers": 2,
        "start_date": "2026-04-18",
        "end_date": "2026-04-18",
        "start_time": "07:30",
        "end_time": "17:30",
        "preferences": ["student-budget"],
        "route": {"distance_km": 382, "drive_minutes": 260, "estimated_arrival_time": "15:30", "route_mode": "fastest"},
        "itinerary": [
            {"time": "09:00", "title": "Autohof fuel + snack", "kind": "fuel", "duration_min": 15},
            {"time": "12:10", "title": "Quick lunch", "kind": "meal", "duration_min": 35},
        ],
        "candidate_places": [],
        "cost_breakdown": {"estimated_total_sgd": 120, "estimated_per_person_sgd": 60, "items": []},
        "is_public": True,
        "created_at": "2026-04-19T08:00:00+00:00",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_trip(trip: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(trip)


def _similarity_score(trip: dict[str, Any], preferences: list[str], adventure_level: int) -> int:
    profile_preferences = set(preferences)
    trip_preferences = set(trip.get("preferences") or [])
    preference_points = len(profile_preferences & trip_preferences) * 12
    level_distance = abs(int(trip.get("adventure_level") or 50) - adventure_level)
    adventure_points = max(0, 24 - round(level_distance / 4))
    mode_points = {"scenic": 4, "balanced": 3, "fastest": 2}.get(trip.get("route_mode"), 0)
    return preference_points + adventure_points + mode_points


class TripRepository:
    """Repository with a Postgres adapter and a safe local fallback."""

    def __init__(self) -> None:
        self._memory: dict[str, dict[str, Any]] = {}
        self._postgres_disabled = False
        self._seed_memory()

    @property
    def database_url(self) -> str | None:
        return os.getenv("DATABASE_URL") or None

    def _seed_memory(self) -> None:
        for trip in EXPLORE_SEED_TRIPS:
            self._memory[trip["id"]] = _copy_trip(trip)

    def _connect(self):
        if not self.database_url or self._postgres_disabled:
            return None
        try:
            import psycopg
        except ImportError:
            self._postgres_disabled = True
            return None
        try:
            connection = psycopg.connect(self.database_url, connect_timeout=2)
            self._ensure_schema(connection)
            return connection
        except Exception:
            self._postgres_disabled = True
            return None

    @staticmethod
    def _ensure_schema(connection) -> None:
        with connection.cursor() as cursor:
            cursor.execute(Path(__file__).with_name("schema.sql").read_text())
        connection.commit()

    @staticmethod
    def _row_to_trip(row: tuple[Any, ...]) -> dict[str, Any]:
        keys = [
            "id", "owner_id", "author_name", "title", "start", "destination", "route_mode",
            "adventure_level", "budget_per_person", "travellers", "start_date", "end_date",
            "start_time", "end_time", "preferences", "route", "itinerary", "candidate_places",
            "cost_breakdown", "is_public", "created_at",
        ]
        trip = dict(zip(keys, row))
        if hasattr(trip.get("created_at"), "isoformat"):
            trip["created_at"] = trip["created_at"].isoformat()
        return trip

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        trip = _copy_trip(payload)
        trip.setdefault("id", str(uuid4()))
        trip.setdefault("owner_id", OWNER_ID)
        trip.setdefault("author_name", "You · Singapore")
        trip.setdefault("created_at", _now())
        trip["updated_at"] = _now()
        connection = self._connect()
        if connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO trips (
                            id, owner_id, author_name, title, start_location, destination, route_mode,
                            adventure_level, budget_per_person, travellers, start_date, end_date,
                            start_time, end_time, preferences, route, itinerary, candidate_places,
                            cost_breakdown, is_public, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title, route = EXCLUDED.route,
                            itinerary = EXCLUDED.itinerary, candidate_places = EXCLUDED.candidate_places,
                            cost_breakdown = EXCLUDED.cost_breakdown, is_public = EXCLUDED.is_public,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            trip["id"], trip["owner_id"], trip.get("author_name"), trip["title"], trip["start"],
                            trip["destination"], trip.get("route_mode", "balanced"), trip.get("adventure_level", 50),
                            trip.get("budget_per_person", 0), trip.get("travellers", 1), trip.get("start_date"),
                            trip.get("end_date"), trip.get("start_time"), trip.get("end_time"),
                            json.dumps(trip.get("preferences", [])), json.dumps(trip.get("route", {})),
                            json.dumps(trip.get("itinerary", [])), json.dumps(trip.get("candidate_places", [])),
                            json.dumps(trip.get("cost_breakdown", {})), trip.get("is_public", False),
                            trip["created_at"], trip["updated_at"],
                        ),
                    )
                connection.commit()
            except Exception:
                self._postgres_disabled = True
            finally:
                connection.close()
        self._memory[trip["id"]] = _copy_trip(trip)
        return _copy_trip(trip)

    def list_saved(self, owner_id: str = OWNER_ID) -> list[dict[str, Any]]:
        connection = self._connect()
        if connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """SELECT id, owner_id, author_name, title, start_location, destination, route_mode,
                        adventure_level, budget_per_person, travellers, start_date, end_date, start_time, end_time,
                        preferences, route, itinerary, candidate_places, cost_breakdown, is_public, created_at
                        FROM trips WHERE owner_id = %s ORDER BY updated_at DESC""",
                        (owner_id,),
                    )
                    rows = [self._row_to_trip(row) for row in cursor.fetchall()]
                connection.close()
                return rows
            except Exception:
                self._postgres_disabled = True
                connection.close()
        return [_copy_trip(trip) for trip in self._memory.values() if trip.get("owner_id") == owner_id and not trip.get("is_public")]

    def get(self, trip_id: str) -> dict[str, Any] | None:
        trip = self._memory.get(trip_id)
        return _copy_trip(trip) if trip else None

    def delete(self, trip_id: str, owner_id: str = OWNER_ID) -> bool:
        trip = self._memory.get(trip_id)
        if not trip or trip.get("owner_id") != owner_id:
            return False
        self._memory.pop(trip_id, None)
        connection = self._connect()
        if connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM trips WHERE id = %s AND owner_id = %s", (trip_id, owner_id))
                connection.commit()
            except Exception:
                self._postgres_disabled = True
            finally:
                connection.close()
        return True

    def list_explore(self, preferences: list[str] | None = None, adventure_level: int = 70, limit: int = 20) -> list[dict[str, Any]]:
        trips_by_id = {trip["id"]: _copy_trip(trip) for trip in self._memory.values() if trip.get("is_public")}
        connection = self._connect()
        if connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """SELECT id, owner_id, author_name, title, start_location, destination, route_mode,
                        adventure_level, budget_per_person, travellers, start_date, end_date, start_time, end_time,
                        preferences, route, itinerary, candidate_places, cost_breakdown, is_public, created_at
                        FROM trips WHERE is_public = TRUE ORDER BY updated_at DESC"""
                    )
                    for row in cursor.fetchall():
                        trip = self._row_to_trip(row)
                        trips_by_id[trip["id"]] = trip
                connection.close()
            except Exception:
                self._postgres_disabled = True
                connection.close()
        trips = list(trips_by_id.values())
        ranked = sorted(
            trips,
            key=lambda trip: _similarity_score(trip, preferences or [], adventure_level),
            reverse=True,
        )
        return [_copy_trip(trip) for trip in ranked[:limit]]


trip_repository = TripRepository()
