"""Route and place providers used by the planner.

Google Maps is used when GOOGLE_MAPS_API_KEY is configured. The demo provider
keeps local development and the UI prototype usable without external keys.
"""

from __future__ import annotations

from collections import defaultdict, deque
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx


GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
GOOGLE_PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places"


def _request_limit(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


GOOGLE_REQUEST_LIMITS = {
    "routes": _request_limit("VIBETRIP_GOOGLE_ROUTES_MAX_PER_MINUTE", 10),
    "places": _request_limit("VIBETRIP_GOOGLE_PLACES_MAX_PER_MINUTE", 30),
    "details": _request_limit("VIBETRIP_GOOGLE_DETAILS_MAX_PER_MINUTE", 20),
}
_google_request_windows: dict[str, deque[float]] = defaultdict(deque)


def _reserve_google_request(kind: str) -> None:
    """Apply a process-local circuit breaker before a billable Google call."""
    now = time.monotonic()
    requests = _google_request_windows[kind]
    while requests and now - requests[0] >= 60:
        requests.popleft()
    limit = GOOGLE_REQUEST_LIMITS[kind]
    if len(requests) >= limit:
        raise RuntimeError(f"Google {kind} request budget reached; using demo fallback until the window resets.")
    requests.append(now)
PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}
FOOD_TYPES = {"restaurant", "cafe", "coffee_shop", "fast_food_restaurant", "meal_takeaway", "bakery"}
ATTRACTION_TYPES = {"tourist_attraction", "museum", "park", "amusement_park", "national_park", "historical_landmark"}
FOOD_COST_BY_LEVEL_SGD = {0: 0, 1: 12, 2: 22, 3: 38, 4: 60}
ROUTE_MODE_CONFIG = {
    "fastest": {
        "label": "Fastest",
        "description": "Bare essentials with minimal route drift.",
        "corridor_types": ("restaurant", "cafe", "gas_station", "convenience_store"),
        "destination_types": ("restaurant", "cafe", "tourist_attraction"),
        "corridor_sample_count": 4,
        "corridor_radius": 2200,
        "destination_radius": 5000,
        "max_results": 4,
    },
    "balanced": {
        "label": "Balanced",
        "description": "A few worthwhile stops without losing the day.",
        "corridor_types": ("tourist_attraction", "restaurant", "cafe", "gas_station", "convenience_store", "park", "museum"),
        "destination_types": ("tourist_attraction", "restaurant", "cafe", "park", "museum"),
        "corridor_sample_count": 5,
        "corridor_radius": 3200,
        "destination_radius": 6500,
        "max_results": 5,
    },
    "scenic": {
        "label": "Scenic",
        "description": "Intermediate cities, viewpoints, and memorable detours.",
        "corridor_types": ("tourist_attraction", "restaurant", "cafe", "gas_station", "convenience_store", "park", "museum", "national_park", "historical_landmark"),
        "destination_types": ("tourist_attraction", "restaurant", "cafe", "park", "museum", "national_park", "historical_landmark"),
        "corridor_sample_count": 7,
        "corridor_radius": 5000,
        "destination_radius": 8500,
        "max_results": 5,
    },
}

GOOGLE_ROUTE_FIELD_MASK = "routes.duration,routes.staticDuration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.travelAdvisory.speedReadingIntervals"
# Keep broad route searches to the fields needed for ranking and scheduling.
# Review text is intentionally fetched only by a future on-demand details view.
GOOGLE_PLACE_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.priceLevel,places.currentOpeningHours,places.regularOpeningHours,places.googleMapsUri,places.websiteUri,places.primaryType,places.types"

SEARCH_STOP_WORDS = {
    "a", "an", "and", "another", "are", "at", "be", "by", "can", "for", "from", "has", "have",
    "i", "in", "is", "it", "like", "maybe", "me", "my", "of", "on", "place", "please", "really",
    "that", "the", "there", "this", "to", "under", "want", "with", "would", "you",
    "around", "close", "closest", "near", "nearer", "nearby", "pit", "pitstop", "stop", "stops", "toward", "towards",
}
SEARCH_FEEDBACK_WORDS = {"dont", "doesnt", "hate", "not", "rather", "instead", "prefer", "looking", "find", "show"}
CUISINE_TERMS = {"chinese", "japanese", "korean", "thai", "indian", "malay", "vietnamese", "mexican", "italian", "mediterranean"}
LOCATION_BOUNDARY_WORDS = {"under", "within", "with", "for", "that", "and", "but", "on"}


def _extract_location_hint(query: str) -> str | None:
    """Extract an explicit locality without asking the ranking model to infer it."""
    patterns = (
        r"\bnearer?\s+to\s+(.+?)(?=\s+(?:under|within|with|for|that|and|but|on)\b|$)",
        r"\bclose\s+to\s+(.+?)(?=\s+(?:under|within|with|for|that|and|but|on)\b|$)",
        r"\b(?:near|around|in|at)\s+(.+?)(?=\s+(?:under|within|with|for|that|and|but|on)\b|$)",
    )
    lowered = query.lower().strip()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        hint = re.sub(r"[^a-z0-9 ]+", " ", match.group(1)).strip()
        tokens = [
            token for token in hint.split()
            if len(token) > 2 and token not in SEARCH_STOP_WORDS | SEARCH_FEEDBACK_WORDS | LOCATION_BOUNDARY_WORDS
        ]
        if tokens:
            return " ".join(tokens[:5])
    return None


def _place_matches_location_hint(candidate: dict[str, Any], location_hint: str | None) -> bool:
    """Apply a conservative locality check after Maps returns candidates."""
    if not location_hint:
        return True
    haystack = " ".join((candidate.get("name", ""), candidate.get("address", ""))).lower()
    tokens = location_hint.split()
    return location_hint in haystack or all(token in haystack for token in tokens)


def _normalize_place_search_query(query: str) -> str:
    """Reduce conversational feedback to a focused Places search phrase."""
    words = [word for word in re.findall(r"[a-z0-9]+", query.lower()) if word not in SEARCH_STOP_WORDS | SEARCH_FEEDBACK_WORDS]
    cuisine = next((word for word in words if word in CUISINE_TERMS), None)
    if cuisine:
        return f"{cuisine} restaurant"
    if any(word in words for word in ("cafe", "coffee", "bakery")):
        return "cafe coffee"
    if any(word in words for word in ("eat", "food", "meal", "meals", "restaurant", "eatery")):
        return "restaurant"
    if any(word in words for word in ("fuel", "gas", "petrol", "snack", "convenience")):
        return "gas station convenience store"
    if any(word in words for word in ("scenic", "scenery", "view", "attraction", "museum", "park")):
        return "scenic attraction"
    return " ".join(words[:8]) or query.strip()


def _place_matches_search_intent(candidate: dict[str, Any], query: str) -> bool:
    """Reject obvious category mismatches while keeping descriptive searches flexible."""
    normalized_query = _normalize_place_search_query(query)
    haystack = " ".join(
        (
            candidate.get("name", ""),
            candidate.get("category", ""),
            candidate.get("reason", ""),
            " ".join(candidate.get("types", [])),
        )
    ).lower()
    cuisine = next((term for term in CUISINE_TERMS if term in normalized_query), None)
    if cuisine:
        return cuisine in haystack
    if normalized_query in {"cafe coffee", "restaurant", "gas station convenience store", "scenic attraction"}:
        category_terms = {
            "cafe coffee": ("cafe", "coffee", "bakery"),
            "restaurant": ("restaurant", "food", "meal", "eatery"),
            "gas station convenience store": ("gas", "fuel", "petrol", "convenience", "store"),
            "scenic attraction": ("attraction", "museum", "park", "scenic", "landmark"),
        }[normalized_query]
        return any(term in haystack for term in category_terms)
    return True


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


def _route_progress_km(location: tuple[float, float], route_points: list[tuple[float, float]]) -> float | None:
    """Approximate a place's distance from the route origin in route order."""
    if not route_points:
        return None
    progress = 0.0
    closest_progress = 0.0
    closest_distance = float("inf")
    for index, point in enumerate(route_points):
        distance = _distance_km(point, location)
        if distance < closest_distance:
            closest_distance = distance
            closest_progress = progress
        if index < len(route_points) - 1:
            progress += _distance_km(point, route_points[index + 1])
    return round(closest_progress, 1)


def _route_segment_bounds(
    route_distance_km: float,
    segment_start_progress_km: float | None,
    segment_end_progress_km: float | None,
) -> tuple[float, float]:
    """Clamp an optional replacement-search window to the active route."""
    lower = 0.0 if segment_start_progress_km is None else float(segment_start_progress_km)
    upper = route_distance_km if segment_end_progress_km is None else float(segment_end_progress_km)
    lower = max(0.0, min(lower, route_distance_km))
    upper = max(0.0, min(upper, route_distance_km))
    return (lower, upper) if lower <= upper else (upper, lower)


def _candidate_in_route_segment(
    candidate: dict[str, Any],
    route_distance_km: float,
    segment_start_progress_km: float | None,
    segment_end_progress_km: float | None,
) -> bool:
    """Keep replacement candidates between the adjacent timeline checkpoints."""
    if segment_start_progress_km is None and segment_end_progress_km is None:
        return True
    progress = candidate.get("route_progress_km")
    if progress is None:
        return False
    lower, upper = _route_segment_bounds(route_distance_km, segment_start_progress_km, segment_end_progress_km)
    # The upper checkpoint belongs to the next timeline row, so do not offer
    # places at or beyond it as replacements for the current row.
    return lower <= float(progress) < upper


def _sort_route_matches(candidates: list[dict[str, Any]], target_progress_km: float | None) -> list[dict[str, Any]]:
    """Make the nearest feasible alternatives appear first, then use enjoyment."""
    if target_progress_km is None:
        return sorted(candidates, key=lambda item: (float(item.get("route_progress_km") or 0), -float(item.get("enjoyment_score") or 0)))
    return sorted(candidates, key=lambda item: (abs(float(item.get("route_progress_km") or 0) - target_progress_km), -float(item.get("enjoyment_score") or 0)))


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


def _review_summary(place: dict[str, Any]) -> tuple[str | None, str | None]:
    review = (place.get("reviews") or [{}])[0]
    text = (review.get("text") or {}).get("text")
    author = (review.get("authorAttribution") or {}).get("displayName")
    return (text[:180] if text else None, author)


def _crowd_risk(place: dict[str, Any]) -> str:
    types = set(place.get("types") or [])
    reviews = int(place.get("userRatingCount") or 0)
    if "tourist_attraction" in types or reviews >= 2500:
        return "high"
    if reviews >= 700 or "restaurant" in types:
        return "medium"
    return "low"


def _cost_metadata(category: str, price_level: int) -> dict[str, Any]:
    normalized_category = category.lower()
    if normalized_category in FOOD_TYPES or "restaurant" in normalized_category or "cafe" in normalized_category:
        amount = FOOD_COST_BY_LEVEL_SGD.get(price_level, 22)
        return {
            "cost_type": "food",
            "estimated_cost_sgd": amount,
            "cost_label": f"~SGD {amount}/person",
            "cost_note": "Estimated from Google price level; check the menu before committing.",
        }
    if normalized_category in ATTRACTION_TYPES or "attraction" in normalized_category or "museum" in normalized_category:
        return {
            "cost_type": "admission",
            "estimated_cost_sgd": None,
            "cost_label": "Ticket price to verify",
            "cost_note": "Google Places does not provide admission pricing for this stop.",
        }
    return {
        "cost_type": "none",
        "estimated_cost_sgd": 0,
        "cost_label": "No entry cost expected",
        "cost_note": "Fuel and tolls are estimated separately.",
    }


def _score_place(
    place: dict[str, Any],
    route_point: tuple[float, float],
    budget_per_person: int,
    crowd_tolerance: str,
    route_mode: str = "balanced",
    recommendation_scope: str = "along_route",
    route_progress_km: float | None = None,
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
    mode_config = ROUTE_MODE_CONFIG.get(route_mode, ROUTE_MODE_CONFIG["balanced"])
    detour_score = max(0, 20 - min(detour_minutes, 40) * 0.5)
    if route_mode == "fastest" and detour_minutes > 8:
        detour_score *= 0.35
    elif route_mode == "balanced" and detour_minutes > 18:
        detour_score *= 0.6
    open_score = 7 if open_now is not False else -18
    crowd = _crowd_risk(place)
    crowd_score = -10 if crowd == "high" and crowd_tolerance == "low" else -4 if crowd == "high" else 3
    scenic = bool(set(place.get("types") or []) & ATTRACTION_TYPES)
    mode_bonus = 8 if route_mode == "scenic" and scenic else 4 if route_mode == "balanced" and scenic else -8 if route_mode == "fastest" and scenic else 0
    destination_bonus = 5 if recommendation_scope == "destination" and route_mode != "fastest" else 0
    enjoyment_score = round(max(0, min(100, rating_score + review_score + budget_score + detour_score + open_score + crowd_score + mode_bonus + destination_bonus)))
    primary_type = place.get("primaryType") or (place.get("types") or ["place"])[0]
    price_label = "Free" if price_level == 0 else "$" * max(1, price_level)
    review_quote, review_author = _review_summary(place)
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
        "recommendation_scope": recommendation_scope,
        "recommendation_kind": "scenic" if scenic else "practical",
        "route_mode": route_mode,
        "google_maps_uri": place.get("googleMapsUri"),
        "website_uri": place.get("websiteUri"),
        "review_quote": review_quote,
        "review_author": review_author,
        "location": {"latitude": location[0], "longitude": location[1]},
        "route_progress_km": route_progress_km,
        "opening_hours": place.get("regularOpeningHours") or {},
        **_cost_metadata(primary_type, price_level),
    }


class DemoMapsProvider:
    async def plan_trip(self, start: str, destination: str, budget_per_person: int, crowd_tolerance: str, start_time: str = "08:10", route_mode: str = "balanced") -> ProviderResult:
        candidates = [
            {"id": "demo-coffee", "name": "The Coffee Exchange", "category": "Cafe", "address": "Providence, RI", "rating": 4.6, "review_count": 825, "price_level": 1, "price_label": "$", "detour_minutes": 3, "enjoyment_score": 86, "crowd_risk": "low", "open_now": True, "route_progress_km": 65, "review_quote": "A calm reset with strong coffee and friendly service.", "review_author": "Demo review", "reason": "A calm reset with strong reviews and almost no route drift."},
            {"id": "demo-attraction", "name": "Mystic Seaport Museum", "category": "Tourist attraction", "address": "Mystic, CT", "rating": 4.7, "review_count": 3200, "price_level": 2, "price_label": "$$", "detour_minutes": 14, "enjoyment_score": 81, "crowd_risk": "high", "open_now": True, "route_progress_km": 180, "review_quote": "Worth arriving early before the afternoon crowd builds.", "review_author": "Demo review", "reason": "High delight potential, but arrive before the afternoon crowd."},
            {"id": "demo-lunch", "name": "The Lobster Shack", "category": "Restaurant", "address": "Mystic, CT", "rating": 4.5, "review_count": 1100, "price_level": 2, "price_label": "$$", "detour_minutes": 12, "enjoyment_score": 88, "crowd_risk": "medium", "open_now": True, "route_progress_km": 205, "review_quote": "The route-friendly lunch stop the group keeps talking about.", "review_author": "Demo review", "reason": "Best balance of a memorable meal, student budget, and route fit."},
            {"id": "demo-fuel", "name": "Shell · Exit 8", "category": "Gas station", "address": "New Haven, CT", "rating": 4.1, "review_count": 410, "price_level": 1, "price_label": "$", "detour_minutes": 2, "enjoyment_score": 72, "crowd_risk": "low", "open_now": True, "route_progress_km": 125, "review_quote": "Low-friction fuel and a clean bathroom stop.", "review_author": "Demo review", "reason": "Low-friction fuel and bathroom stop before the final leg."},
            {"id": "demo-destination", "name": "Brooklyn Bridge Park", "category": "Tourist attraction", "address": "Brooklyn, NY", "rating": 4.8, "review_count": 8400, "price_level": 0, "price_label": "Free", "detour_minutes": 6, "enjoyment_score": 84, "crowd_risk": "high", "open_now": True, "route_progress_km": 340, "review_quote": "A strong first look at the city after the drive.", "review_author": "Demo review", "reason": "A free destination highlight with skyline views."},
        ]
        for candidate in candidates:
            category = candidate["category"].lower().replace(" ", "_")
            candidate.update(_cost_metadata(category, candidate["price_level"]))
            candidate.update({"route_mode": route_mode, "recommendation_kind": "scenic" if "attraction" in category else "practical", "recommendation_scope": "destination" if candidate["id"] == "demo-destination" else "along_route"})
        return ProviderResult(
            route={"distance_km": 348, "drive_minutes": 229, "static_drive_minutes": 218, "traffic_delay_minutes": 11, "traffic_status": "slow", "traffic_note": "Live traffic estimate from the route provider.", "construction_status": "not_available", "summary": f"{start} to {destination}", "stops_needed": ["fuel", "bathroom", "meal"], "route_mode": route_mode, "route_mode_label": ROUTE_MODE_CONFIG.get(route_mode, ROUTE_MODE_CONFIG["balanced"])["label"]},
            candidates=candidates,
            provider="demo",
            warning="GOOGLE_MAPS_API_KEY is not configured; showing demo candidates.",
        )

    async def reroute_with_stops(self, start: str, destination: str, route: dict[str, Any], stops: list[dict[str, Any]], start_time: str = "08:10") -> dict[str, Any]:
        """Keep the demo route usable while making its waypoint intent explicit."""
        waypoint_ids = [stop.get("id") for stop in stops if stop.get("id")]
        return {
            **route,
            "routed_waypoint_ids": waypoint_ids,
            "waypoint_note": f"Demo route reserves {len(waypoint_ids)} planned stop(s); connect Google Maps for live waypoint geometry.",
        }

    async def search_route_places(
        self,
        query: str,
        start: str,
        destination: str,
        budget_per_person: int,
        crowd_tolerance: str,
        route_mode: str = "balanced",
        segment_start_progress_km: float | None = None,
        segment_end_progress_km: float | None = None,
        target_progress_km: float | None = None,
    ) -> ProviderResult:
        result = await self.plan_trip(start, destination, budget_per_person, crowd_tolerance, route_mode=route_mode)
        normalized_query = _normalize_place_search_query(query)
        location_hint = _extract_location_hint(query)
        query_terms = [term for term in re.findall(r"[a-z0-9]+", normalized_query.lower()) if len(term) > 2]
        route_distance_km = float(result.route.get("distance_km") or 0)
        matches = [
            candidate
            for candidate in result.candidates
            if _candidate_in_route_segment(candidate, route_distance_km, segment_start_progress_km, segment_end_progress_km)
            and _place_matches_search_intent(candidate, normalized_query)
            and _place_matches_location_hint(candidate, location_hint)
            and (not query_terms or any(term in " ".join((candidate.get("name", ""), candidate.get("category", ""), candidate.get("reason", ""))).lower() for term in query_terms))
        ]
        matches = _sort_route_matches(matches, target_progress_km)
        warning = result.warning
        if not matches:
            location_message = f" near {location_hint}" if location_hint else ""
            warning = f"{warning + ' ' if warning else ''}No route places matched “{query}”{location_message}. Try a broader request or choose a checkpoint closer to that area."
        return ProviderResult(route=result.route, candidates=matches, provider="demo", warning=warning)


class GoogleMapsProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    @staticmethod
    def _route_payload(start: str, destination: str, stops: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload = {
            "origin": {"address": start},
            "destination": {"address": destination},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": False,
            "extraComputations": ["TRAFFIC_ON_POLYLINE"],
        }
        intermediates = [
            {
                "location": {
                    "latLng": {
                        "latitude": stop["location"]["latitude"],
                        "longitude": stop["location"]["longitude"],
                    }
                }
            }
            for stop in (stops or [])
            if stop.get("location", {}).get("latitude") is not None and stop.get("location", {}).get("longitude") is not None
        ]
        if intermediates:
            payload["intermediates"] = intermediates
        return payload

    @staticmethod
    def _parse_route(route: dict[str, Any], start: str, destination: str, route_mode: str, base_route: dict[str, Any] | None = None) -> dict[str, Any]:
        mode_config = ROUTE_MODE_CONFIG.get(route_mode, ROUTE_MODE_CONFIG["balanced"])
        result = {
            **(base_route or {}),
            "distance_km": round((route.get("distanceMeters") or 0) / 1000),
            "drive_minutes": round(_duration_seconds(route.get("duration")) / 60),
            "static_drive_minutes": round(_duration_seconds(route.get("staticDuration")) / 60),
            "summary": f"{start} to {destination}",
            "stops_needed": ["fuel", "bathroom", "meal"],
            "route_mode": route_mode,
            "route_mode_label": mode_config["label"],
            "route_mode_description": mode_config["description"],
            "polyline": route.get("polyline", {}).get("encodedPolyline"),
        }
        traffic_intervals = (route.get("travelAdvisory") or {}).get("speedReadingIntervals") or []
        traffic_speeds = {interval.get("speed") for interval in traffic_intervals}
        result["traffic_status"] = "heavy" if "TRAFFIC_JAM" in traffic_speeds else "slow" if "SLOW" in traffic_speeds else "light"
        result["traffic_delay_minutes"] = max(0, result["drive_minutes"] - result["static_drive_minutes"])
        result["traffic_intervals"] = traffic_intervals
        result["traffic_note"] = "Live traffic estimate from Google speed intervals."
        result["construction_status"] = "not_available"
        return result

    async def plan_trip(self, start: str, destination: str, budget_per_person: int, crowd_tolerance: str, start_time: str = "08:10", route_mode: str = "balanced") -> ProviderResult:
        mode_config = ROUTE_MODE_CONFIG.get(route_mode, ROUTE_MODE_CONFIG["balanced"])
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": GOOGLE_ROUTE_FIELD_MASK,
        }
        route_payload = self._route_payload(start, destination)
        async with httpx.AsyncClient(timeout=18) as client:
            _reserve_google_request("routes")
            route_response = await client.post(GOOGLE_ROUTES_URL, headers=headers, json=route_payload)
            route_response.raise_for_status()
            route_data = route_response.json()
            route = (route_data.get("routes") or [{}])[0]
            if not route:
                raise RuntimeError("Google Routes returned no route")
            route_result = self._parse_route(route, start, destination, route_mode)
            route_geometry = _decode_polyline(route_result.get("polyline") or "")
            route_points = _sample_polyline(route_geometry, count=mode_config["corridor_sample_count"])
            candidates: dict[str, dict[str, Any]] = {}
            places_headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": GOOGLE_PLACE_FIELD_MASK,
            }
            search_specs = [(point, "along_route", mode_config["corridor_radius"]) for point in (route_points[1:-1] or route_points)]
            if route_points:
                search_specs.append((route_points[-1], "destination", mode_config["destination_radius"]))
            for route_point, recommendation_scope, radius in search_specs:
                search_types = mode_config["destination_types"] if recommendation_scope == "destination" else mode_config["corridor_types"]
                payload = {
                    # Batch categories per corridor point instead of paying for
                    # one Nearby Search request per category.
                    "includedTypes": list(search_types),
                    "maxResultCount": mode_config["max_results"],
                    "rankPreference": "POPULARITY",
                    "locationRestriction": {"circle": {"center": {"latitude": route_point[0], "longitude": route_point[1]}, "radius": radius}},
                }
                _reserve_google_request("places")
                response = await client.post(GOOGLE_PLACES_URL, headers=places_headers, json=payload)
                response.raise_for_status()
                for place in response.json().get("places", []):
                    location = _place_location(place)
                    normalized = _score_place(
                        place,
                        route_point,
                        budget_per_person,
                        crowd_tolerance,
                        route_mode,
                        recommendation_scope,
                        _route_progress_km(location, route_geometry) if location else None,
                    )
                    if normalized and normalized["id"] not in candidates:
                        candidates[normalized["id"]] = normalized
        return ProviderResult(route=route_result, candidates=sorted(candidates.values(), key=lambda item: item["enjoyment_score"], reverse=True), provider="google")

    async def search_route_places(
        self,
        query: str,
        start: str,
        destination: str,
        budget_per_person: int,
        crowd_tolerance: str,
        route_mode: str = "balanced",
        segment_start_progress_km: float | None = None,
        segment_end_progress_km: float | None = None,
        target_progress_km: float | None = None,
    ) -> ProviderResult:
        """Search a free-form request at several points along the live route."""
        normalized_query = _normalize_place_search_query(query)
        location_hint = _extract_location_hint(query)
        maps_query = f"{normalized_query} near {location_hint}" if location_hint else normalized_query
        mode_config = ROUTE_MODE_CONFIG.get(route_mode, ROUTE_MODE_CONFIG["balanced"])
        route_headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": GOOGLE_ROUTE_FIELD_MASK,
        }
        places_headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": GOOGLE_PLACE_FIELD_MASK,
        }
        async with httpx.AsyncClient(timeout=18) as client:
            _reserve_google_request("routes")
            route_response = await client.post(GOOGLE_ROUTES_URL, headers=route_headers, json=self._route_payload(start, destination))
            route_response.raise_for_status()
            route_data = route_response.json()
            raw_route = (route_data.get("routes") or [{}])[0]
            if not raw_route:
                raise RuntimeError("Google Routes returned no route for place search")
            route_result = self._parse_route(raw_route, start, destination, route_mode)
            route_geometry = _decode_polyline(route_result.get("polyline") or "")
            route_distance_km = float(route_result.get("distance_km") or 0)
            route_points = _sample_polyline(route_geometry, count=min(5, mode_config["corridor_sample_count"]))
            if segment_start_progress_km is not None or segment_end_progress_km is not None:
                lower, upper = _route_segment_bounds(route_distance_km, segment_start_progress_km, segment_end_progress_km)
                segment_points = [
                    point for point in route_points
                    if lower <= float(_route_progress_km(point, route_geometry) or 0) < upper
                ]
                if segment_points:
                    route_points = segment_points
                elif route_points:
                    target = target_progress_km if target_progress_km is not None else lower
                    route_points = [min(route_points, key=lambda point: abs(float(_route_progress_km(point, route_geometry) or 0) - target))]
            candidates: dict[str, dict[str, Any]] = {}
            # When the user names a locality, let Places resolve that locality
            # directly. A sparse route-point bias can otherwise anchor the
            # search near the selected checkpoint (for example Yong Peng) and
            # miss an earlier but still valid locality such as Johor Bahru.
            # Actual route geometry and segment bounds below remain the source
            # of truth for whether a result can replace this stop.
            search_points = [route_points[0] if route_points else (0.0, 0.0)] if location_hint else (route_points[1:-1] or route_points)
            for route_point in search_points:
                payload = {
                    "textQuery": maps_query,
                    "maxResultCount": 5,
                    "rankPreference": "RELEVANCE",
                }
                if not location_hint:
                    payload["locationBias"] = {"circle": {"center": {"latitude": route_point[0], "longitude": route_point[1]}, "radius": mode_config["corridor_radius"]}}
                _reserve_google_request("places")
                response = await client.post(GOOGLE_TEXT_SEARCH_URL, headers=places_headers, json=payload)
                response.raise_for_status()
                for place in response.json().get("places", []):
                    location = _place_location(place)
                    normalized = _score_place(
                        place,
                        route_point,
                        budget_per_person,
                        crowd_tolerance,
                        route_mode,
                        "along_route",
                        _route_progress_km(location, route_geometry) if location else None,
                    )
                    if normalized:
                        normalized["types"] = place.get("types") or []
                    if normalized and _candidate_in_route_segment(normalized, route_distance_km, segment_start_progress_km, segment_end_progress_km) and _place_matches_search_intent(normalized, normalized_query) and _place_matches_location_hint(normalized, location_hint) and normalized["id"] not in candidates:
                        candidates[normalized["id"]] = normalized
        results = _sort_route_matches(list(candidates.values()), target_progress_km)
        location_message = f" near {location_hint}" if location_hint else ""
        warning = None if results else f"No route places matched “{query}”{location_message}. Try a broader request or choose a checkpoint closer to that area."
        return ProviderResult(route=route_result, candidates=results, provider="google", warning=warning)

    async def reroute_with_stops(self, start: str, destination: str, route: dict[str, Any], stops: list[dict[str, Any]], start_time: str = "08:10") -> dict[str, Any]:
        """Recompute the route so selected places are actual navigation waypoints."""
        waypoint_stops = [
            stop for stop in stops
            if stop.get("location", {}).get("latitude") is not None and stop.get("location", {}).get("longitude") is not None
        ]
        if not waypoint_stops:
            return route
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": GOOGLE_ROUTE_FIELD_MASK,
        }
        async with httpx.AsyncClient(timeout=18) as client:
            _reserve_google_request("routes")
            response = await client.post(
                GOOGLE_ROUTES_URL,
                headers=headers,
                json=self._route_payload(start, destination, waypoint_stops),
            )
            response.raise_for_status()
            route_data = response.json()
        routed = (route_data.get("routes") or [{}])[0]
        if not routed:
            raise RuntimeError("Google Routes returned no waypoint route")
        route_result = self._parse_route(routed, start, destination, route.get("route_mode", "balanced"), route)
        waypoint_ids = [stop.get("id") for stop in waypoint_stops if stop.get("id")]
        route_result["routed_waypoint_ids"] = waypoint_ids
        route_result["waypoint_note"] = f"Route plotted through {len(waypoint_ids)} planned stop(s)."
        return route_result

    async def suggest_cities(self, query: str, session_token: str | None = None) -> list[dict[str, str]]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "suggestions.placePrediction.placeId,suggestions.placePrediction.text,suggestions.placePrediction.structuredFormat",
        }
        # Endpoints may be campuses, hotels, attractions, or exact addresses;
        # restricting autocomplete to cities makes the route look precise while
        # still routing from an ambiguous centroid.
        payload = {"input": query, "languageCode": "en"}
        if session_token:
            payload["sessionToken"] = session_token
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(GOOGLE_AUTOCOMPLETE_URL, headers=headers, json=payload)
            response.raise_for_status()
            suggestions = response.json().get("suggestions", [])
        normalized = []
        for suggestion in suggestions:
            prediction = suggestion.get("placePrediction") or {}
            text = prediction.get("text", {}).get("text")
            if not text:
                continue
            structured = prediction.get("structuredFormat") or {}
            normalized.append({
                "id": prediction.get("placeId") or prediction.get("place", text),
                "text": text,
                "main_text": (structured.get("mainText") or {}).get("text") or text,
                "secondary_text": (structured.get("secondaryText") or {}).get("text") or "",
            })
        return normalized

    async def place_details(self, place_id: str, session_token: str | None = None) -> dict[str, Any] | None:
        """Resolve a selected autocomplete prediction to its canonical address."""
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "id,displayName,formattedAddress,location,googleMapsUri",
        }
        async with httpx.AsyncClient(timeout=8) as client:
            _reserve_google_request("details")
            response = await client.get(
                f"{GOOGLE_PLACE_DETAILS_URL}/{place_id}",
                headers=headers,
                params={"sessionToken": session_token} if session_token else None,
            )
            response.raise_for_status()
            place = response.json()
        display_name = (place.get("displayName") or {}).get("text") or place.get("formattedAddress")
        formatted_address = place.get("formattedAddress") or display_name
        if not formatted_address:
            return None
        return {
            "id": place.get("id") or place_id,
            "text": formatted_address,
            "main_text": display_name or formatted_address,
            "secondary_text": formatted_address,
            "formatted_address": formatted_address,
            "location": place.get("location") or {},
            "google_maps_uri": place.get("googleMapsUri") or "",
        }


async def suggest_cities(query: str, session_token: str | None = None) -> list[dict[str, str]]:
    """Return endpoint suggestions with a deterministic local fallback."""
    provider = get_maps_provider()
    if isinstance(provider, GoogleMapsProvider):
        return await provider.suggest_cities(query, session_token)
    hints = [
        {"id": "demo-boston-university", "text": "Boston University, 233 Bay State Road, Boston, MA, USA", "main_text": "Boston University", "secondary_text": "233 Bay State Road, Boston, MA, USA"},
        {"id": "demo-boston-ma", "text": "Boston, Massachusetts, USA", "main_text": "Boston", "secondary_text": "Massachusetts, USA"},
        {"id": "demo-boston-uk", "text": "Boston, Lincolnshire, UK", "main_text": "Boston", "secondary_text": "Lincolnshire, UK"},
        {"id": "demo-empire-state-building", "text": "Empire State Building, 350 5th Avenue, New York, NY 10118, USA", "main_text": "Empire State Building", "secondary_text": "350 5th Avenue, New York, NY 10118, USA"},
        {"id": "demo-new-york", "text": "New York, New York, USA", "main_text": "New York", "secondary_text": "New York, USA"},
        {"id": "demo-hoxton-williamsburg", "text": "The Hoxton Williamsburg, 97 Wythe Avenue, Brooklyn, NY, USA", "main_text": "The Hoxton Williamsburg", "secondary_text": "97 Wythe Avenue, Brooklyn, NY, USA"},
        {"id": "demo-singapore", "text": "Singapore", "main_text": "Singapore", "secondary_text": "Singapore"},
        {"id": "demo-kuala-lumpur", "text": "Kuala Lumpur, Malaysia", "main_text": "Kuala Lumpur", "secondary_text": "Malaysia"},
    ]
    normalized_query = query.lower().strip()
    matches = [hint for hint in hints if normalized_query in hint["text"].lower() or normalized_query in hint["main_text"].lower()]
    return sorted(
        matches,
        key=lambda hint: (
            hint["main_text"].lower() != normalized_query,
            not hint["main_text"].lower().startswith(normalized_query),
        ),
    )[:5]


async def place_details(place_id: str, session_token: str | None = None) -> dict[str, Any] | None:
    """Resolve a place ID using Google or a deterministic local fallback."""
    provider = get_maps_provider()
    if isinstance(provider, GoogleMapsProvider):
        return await provider.place_details(place_id, session_token)
    fallback_details = {
        "demo-boston-university": {"id": "demo-boston-university", "text": "Boston University, 233 Bay State Road, Boston, MA, USA", "main_text": "Boston University", "secondary_text": "233 Bay State Road, Boston, MA, USA"},
        "demo-empire-state-building": {"id": "demo-empire-state-building", "text": "Empire State Building, 350 5th Avenue, New York, NY 10118, USA", "main_text": "Empire State Building", "secondary_text": "350 5th Avenue, New York, NY 10118, USA"},
        "demo-hoxton-williamsburg": {"id": "demo-hoxton-williamsburg", "text": "The Hoxton Williamsburg, 97 Wythe Avenue, Brooklyn, NY, USA", "main_text": "The Hoxton Williamsburg", "secondary_text": "97 Wythe Avenue, Brooklyn, NY, USA"},
    }
    return fallback_details.get(place_id)


def get_maps_provider() -> GoogleMapsProvider | DemoMapsProvider:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    live_maps_enabled = os.getenv("VIBETRIP_LIVE_MAPS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    return GoogleMapsProvider(api_key) if api_key and live_maps_enabled else DemoMapsProvider()
