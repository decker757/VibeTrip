"""Route and place providers used by the planner.

Google Maps is used when GOOGLE_MAPS_API_KEY is configured. The demo provider
keeps local development and the UI prototype usable without external keys.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx


GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}
SEARCH_TYPES = ("tourist_attraction", "restaurant", "cafe", "gas_station")


@dataclass
class ProviderResult:
    route: dict[str, Any]
    candidates: list[dict[str, Any]]
    provider: str
    warning: str | None = None


def _duration_seconds(value: str | None) -> int:
    match = re.search(r"(\d+)s", value or "")
    return int(match.group(1)) if match else 0


def _decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode Google's encoded polyline into latitude/longitude pairs."""
    points: list[tuple[float, float]] = []
    index = latitude = longitude = 0
    while index < len(encoded):
        result = shift = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        latitude += ~(result >> 1) if result & 1 else result >> 1
        result = shift = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        longitude += ~(result >> 1) if result & 1 else result >> 1
        points.append((latitude / 1e5, longitude / 1e5))
    return points


def _sample_polyline(points: list[tuple[float, float]], count: int = 4) -> list[tuple[float, float]]:
    if not points:
        return []
    if len(points) <= count:
        return points
    indices = [round(i * (len(points) - 1) / (count - 1)) for i in range(count)]
    return [points[index] for index in indices]


def _distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    radius = 6371
    lat_one, lon_one = map(math.radians, first)
    lat_two, lon_two = map(math.radians, second)
    delta_lat = lat_two - lat_one
    delta_lon = lon_two - lon_one
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat_one) * math.cos(lat_two) * math.sin(delta_lon / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(a))


def _display_name(place: dict[str, Any]) -> str:
    return place.get("displayName", {}).get("text") or "Unnamed place"


def _place_location(place: dict[str, Any]) -> tuple[float, float] | None:
    location = place.get("location") or {}
    if "latitude" not in location or "longitude" not in location:
        return None
    return float(location["latitude"]), float(location["longitude"])


def _crowd_risk(place: dict[str, Any]) -> str:
    types = set(place.get("types") or [])
    reviews = int(place.get("userRatingCount") or 0)
    if "tourist_attraction" in types or reviews >= 2500:
        return "high"
    if reviews >= 700 or "restaurant" in types:
        return "medium"
    return "low"


def _score_place(
    place: dict[str, Any],
    route_point: tuple[float, float],
    budget_per_person: int,
    crowd_tolerance: str,
) -> dict[str, Any] | None:
    location = _place_location(place)
    if not location:
        return None
    price_level = PRICE_LEVELS.get(place.get("priceLevel"), 1)
    rating = float(place.get("rating") or 0)
    review_count = int(place.get("userRatingCount") or 0)
    open_now = (place.get("currentOpeningHours") or {}).get("openNow")
    detour_minutes = round((_distance_km(route_point, location) * 2 / 45) * 60)
    budget_tier = 1 if budget_per_person < 100 else 2 if budget_per_person < 250 else 3
    rating_score = (rating / 5) * 35
    review_score = min(math.log10(max(review_count, 1)) / 4, 1) * 15
    budget_score = max(0, 18 - abs(price_level - budget_tier) * 7)
    detour_score = max(0, 20 - min(detour_minutes, 35) * 0.55)
    open_score = 7 if open_now is not False else -18
    crowd = _crowd_risk(place)
    crowd_score = -10 if crowd == "high" and crowd_tolerance == "low" else -4 if crowd == "high" else 3
    enjoyment_score = round(max(0, min(100, rating_score + review_score + budget_score + detour_score + open_score + crowd_score)))
    primary_type = place.get("primaryType") or (place.get("types") or ["place"])[0]
    price_label = "$" * max(1, price_level)
    return {
        "id": place.get("id") or _display_name(place),
        "name": _display_name(place),
        "category": primary_type.replace("_", " ").title(),
        "address": place.get("formattedAddress") or "Along the route",
        "rating": rating,
        "review_count": review_count,
        "price_level": price_level,
        "price_label": price_label,
        "detour_minutes": detour_minutes,
        "enjoyment_score": enjoyment_score,
        "crowd_risk": crowd,
        "open_now": open_now is not False,
        "reason": f"{rating:.1f} rating, {price_label} pricing, and an estimated {detour_minutes}-minute detour.",
        "google_maps_uri": place.get("googleMapsUri"),
        "location": {"latitude": location[0], "longitude": location[1]},
    }


class DemoMapsProvider:
    async def plan_trip(self, start: str, destination: str, budget_per_person: int, crowd_tolerance: str) -> ProviderResult:
        candidates = [
            {"id": "demo-coffee", "name": "The Coffee Exchange", "category": "Cafe", "address": "Providence, RI", "rating": 4.6, "review_count": 825, "price_level": 1, "price_label": "$", "detour_minutes": 3, "enjoyment_score": 86, "crowd_risk": "low", "open_now": True, "reason": "A calm reset with strong reviews and almost no route drift."},
            {"id": "demo-attraction", "name": "Mystic Seaport Museum", "category": "Tourist attraction", "address": "Mystic, CT", "rating": 4.7, "review_count": 3200, "price_level": 2, "price_label": "$$", "detour_minutes": 14, "enjoyment_score": 81, "crowd_risk": "high", "open_now": True, "reason": "High delight potential, but arrive before the afternoon crowd."},
            {"id": "demo-lunch", "name": "The Lobster Shack", "category": "Restaurant", "address": "Mystic, CT", "rating": 4.5, "review_count": 1100, "price_level": 2, "price_label": "$$", "detour_minutes": 12, "enjoyment_score": 88, "crowd_risk": "medium", "open_now": True, "reason": "Best balance of a memorable meal, student budget, and route fit."},
            {"id": "demo-fuel", "name": "Shell · Exit 8", "category": "Gas station", "address": "New Haven, CT", "rating": 4.1, "review_count": 410, "price_level": 1, "price_label": "$", "detour_minutes": 2, "enjoyment_score": 72, "crowd_risk": "low", "open_now": True, "reason": "Low-friction fuel and bathroom stop before the final leg."},
        ]
        return ProviderResult(
            route={"distance_km": 348, "drive_minutes": 229, "summary": f"{start} to {destination}", "stops_needed": ["fuel", "bathroom", "meal"]},
            candidates=candidates,
            provider="demo",
            warning="GOOGLE_MAPS_API_KEY is not configured; showing demo candidates.",
        )


class GoogleMapsProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def plan_trip(self, start: str, destination: str, budget_per_person: int, crowd_tolerance: str) -> ProviderResult:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
        }
        route_payload = {
            "origin": {"address": start},
            "destination": {"address": destination},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": False,
        }
        async with httpx.AsyncClient(timeout=18) as client:
            route_response = await client.post(GOOGLE_ROUTES_URL, headers=headers, json=route_payload)
            route_response.raise_for_status()
            route_data = route_response.json()
            route = (route_data.get("routes") or [{}])[0]
            if not route:
                raise RuntimeError("Google Routes returned no route")
            route_result = {
                "distance_km": round((route.get("distanceMeters") or 0) / 1000),
                "drive_minutes": round(_duration_seconds(route.get("duration")) / 60),
                "summary": f"{start} to {destination}",
                "stops_needed": ["fuel", "bathroom", "meal"],
                "polyline": route.get("polyline", {}).get("encodedPolyline"),
            }
            route_points = _sample_polyline(route_result.get("polyline") or "", count=4)
            candidates: dict[str, dict[str, Any]] = {}
            places_headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.priceLevel,places.currentOpeningHours,places.googleMapsUri,places.primaryType,places.types",
            }
            for route_point in route_points[1:-1] or route_points:
                for place_type in SEARCH_TYPES:
                    payload = {
                        "includedTypes": [place_type],
                        "maxResultCount": 5,
                        "rankPreference": "POPULARITY",
                        "locationRestriction": {"circle": {"center": {"latitude": route_point[0], "longitude": route_point[1]}, "radius": 3000}},
                    }
                    response = await client.post(GOOGLE_PLACES_URL, headers=places_headers, json=payload)
                    response.raise_for_status()
                    for place in response.json().get("places", []):
                        normalized = _score_place(place, route_point, budget_per_person, crowd_tolerance)
                        if normalized and normalized["id"] not in candidates:
                            candidates[normalized["id"]] = normalized
        return ProviderResult(route=route_result, candidates=sorted(candidates.values(), key=lambda item: item["enjoyment_score"], reverse=True), provider="google")


def get_maps_provider() -> GoogleMapsProvider | DemoMapsProvider:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    return GoogleMapsProvider(api_key) if api_key else DemoMapsProvider()
