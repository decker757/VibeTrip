import httpx

from backend import providers
from backend.providers import DemoMapsProvider, GoogleMapsProvider, _candidate_in_route_segment, _score_place


def test_segment_lower_bound_inclusive_upper_exclusive():
    assert _candidate_in_route_segment({"route_progress_km": 100}, 348, 100, 200)
    assert not _candidate_in_route_segment({"route_progress_km": 200}, 348, 100, 200)


def test_segment_rejects_missing_progress_when_bounded():
    assert not _candidate_in_route_segment({"route_progress_km": None}, 348, 0, 200)
    assert _candidate_in_route_segment({"route_progress_km": None}, 348, None, None)


def _google_place(open_now: bool = True, lat: float = 1.30) -> dict:
    return {
        "id": "p1",
        "displayName": {"text": "Test Cafe"},
        "location": {"latitude": lat, "longitude": 103.80},
        "rating": 4.5,
        "userRatingCount": 500,
        "priceLevel": "PRICE_LEVEL_INEXPENSIVE",
        "currentOpeningHours": {"openNow": open_now},
        "primaryType": "cafe",
        "types": ["cafe"],
    }


def test_closed_place_scores_lower_than_open():
    point = (1.30, 103.80)
    opened = _score_place(_google_place(True), point, 400, "medium")
    closed = _score_place(_google_place(False), point, 400, "medium")
    assert closed["enjoyment_score"] < opened["enjoyment_score"] and closed["open_now"] is False


def test_fastest_penalises_long_detour():
    point = (1.30, 103.80)
    far = _google_place(lat=1.40)  # ~11 km away, well over an 8-minute detour
    assert _score_place(far, point, 400, "medium", "fastest")["enjoyment_score"] < _score_place(far, point, 400, "medium", "balanced")["enjoyment_score"]


async def test_demo_text_search_respects_segment():
    p = DemoMapsProvider()
    g = await p.route_geometry("A", "B", "balanced")
    ids = [c["id"] for c in await p.search_places_text(g, "cozy coffee spot", "cafe coffee", None, 400, "medium", "balanced", 0, 100, 65)]
    assert ids == ["demo-coffee"]


async def test_demo_text_search_other_category_returns_all_in_segment():
    p = DemoMapsProvider()
    g = await p.route_geometry("A", "B", "balanced")
    ids = {c["id"] for c in await p.search_places_text(g, "anything nice", "", None, 400, "medium", "balanced", 100, 210, None)}
    assert ids == {"demo-fuel", "demo-attraction", "demo-lunch"}


def _encode_polyline(points):
    out, last_lat, last_lng = "", 0, 0
    for lat, lng in points:
        for value, last in ((round(lat * 1e5), last_lat), (round(lng * 1e5), last_lng)):
            delta = value - last
            delta = ~(delta << 1) if delta < 0 else delta << 1
            while delta >= 0x20:
                out += chr((0x20 | (delta & 0x1F)) + 63)
                delta >>= 5
            out += chr(delta + 63)
        last_lat, last_lng = round(lat * 1e5), round(lng * 1e5)
    return out


async def test_google_search_route_places_uses_one_routes_call(monkeypatch):
    urls: list[str] = []
    polyline = _encode_polyline([(1.30 + i * 0.05, 103.80) for i in range(10)])

    async def fake_post(self, url, **kwargs):
        urls.append(url)
        if url == providers.GOOGLE_ROUTES_URL:
            body = {"routes": [{"distanceMeters": 50000, "duration": "3000s", "staticDuration": "2800s", "polyline": {"encodedPolyline": polyline}}]}
        else:
            body = {"places": [{**_google_place(lat=1.55), "id": f"p{len(urls)}"}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(providers, "_google_request_windows", providers.defaultdict(providers.deque))
    result = await GoogleMapsProvider("test-key").search_route_places("coffee", "A", "B", 400, "medium")
    assert urls.count(providers.GOOGLE_ROUTES_URL) == 1
    assert urls.count(providers.GOOGLE_TEXT_SEARCH_URL) >= 1
    assert result.provider == "google" and result.candidates


def test_sample_polyline_spaces_points_by_distance_not_vertex_count():
    # 100 vertices packed into the first ~1 km (a twisty mountain road), then two long straight legs.
    dense = [(0.0, 0.0001 * i) for i in range(100)]
    points = dense + [(0.0, 1.0), (0.0, 2.0)]
    samples = providers._sample_polyline(points, count=3)
    assert samples[0] == points[0] and samples[-1] == points[-1]
    assert samples[1] == (0.0, 1.0)  # vertex-index sampling would pick a point inside the dense cluster


def _place(id, primary_type, lat):
    return {**_google_place(lat=lat), "id": id, "displayName": {"text": id}, "primaryType": primary_type, "types": [primary_type]}


async def test_balanced_plan_backfills_fuel_and_food_when_corridor_search_is_empty(monkeypatch):
    # A sparse rural route: the broad corridor search finds nothing along the way.
    polyline = _encode_polyline([(1.30 + i * 0.5, 103.80) for i in range(10)])
    calls: list[list[str]] = []

    async def fake_post(self, url, **kwargs):
        if url == providers.GOOGLE_ROUTES_URL:
            body = {"routes": [{"distanceMeters": 500000, "duration": "21600s", "staticDuration": "21000s", "polyline": {"encodedPolyline": polyline}}]}
        else:
            types = kwargs["json"]["includedTypes"]
            calls.append(types)
            point = kwargs["json"]["locationRestriction"]["circle"]["center"]["latitude"]
            body = {"places": [_place(f"gas-{point}", "gas_station", point)] if types == ["gas_station"]
                    else [_place(f"food-{point}", "restaurant", point)] if types == ["restaurant"] else []}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(providers, "_google_request_windows", providers.defaultdict(providers.deque))
    result = await GoogleMapsProvider("test-key").plan_trip("A", "B", 400, "medium", "08:10", "balanced")
    categories = {c["category"] for c in result.candidates if c["recommendation_scope"] == "along_route"}
    assert "Gas Station" in categories and "Restaurant" in categories
    assert ["gas_station"] in calls and ["restaurant"] in calls


async def test_balanced_plan_skips_backfill_when_corridor_already_has_fuel_and_food(monkeypatch):
    polyline = _encode_polyline([(1.30 + i * 0.5, 103.80) for i in range(10)])
    calls: list[list[str]] = []

    async def fake_post(self, url, **kwargs):
        if url == providers.GOOGLE_ROUTES_URL:
            body = {"routes": [{"distanceMeters": 500000, "duration": "21600s", "staticDuration": "21000s", "polyline": {"encodedPolyline": polyline}}]}
        else:
            calls.append(kwargs["json"]["includedTypes"])
            point = kwargs["json"]["locationRestriction"]["circle"]["center"]["latitude"]
            body = {"places": [_place(f"gas-{point}", "gas_station", point), _place(f"food-{point}", "restaurant", point)]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(providers, "_google_request_windows", providers.defaultdict(providers.deque))
    await GoogleMapsProvider("test-key").plan_trip("A", "B", 400, "medium", "08:10", "balanced")
    assert ["gas_station"] not in calls and ["restaurant"] not in calls  # no extra billable requests


async def test_backfill_runs_only_for_points_missing_fuel_or_food(monkeypatch):
    # Only the first corridor point has fuel and food; the other two are empty stretches.
    polyline = _encode_polyline([(1.30 + i * 0.5, 103.80) for i in range(10)])
    corridor_points: list[float] = []
    backfills: list[tuple[str, float]] = []

    async def fake_post(self, url, **kwargs):
        if url == providers.GOOGLE_ROUTES_URL:
            body = {"routes": [{"distanceMeters": 500000, "duration": "21600s", "staticDuration": "21000s", "polyline": {"encodedPolyline": polyline}}]}
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))
        payload = kwargs["json"]
        circle = payload["locationRestriction"]["circle"]
        lat = circle["center"]["latitude"]
        if len(payload["includedTypes"]) == 1:
            backfills.append((payload["includedTypes"][0], lat))
            places = []
        elif circle["radius"] == providers.ROUTE_MODE_CONFIG["balanced"]["corridor_radius"]:
            corridor_points.append(lat)
            places = [_place(f"gas-{lat}", "gas_station", lat), _place(f"food-{lat}", "restaurant", lat)] if len(corridor_points) == 1 else []
        else:
            places = []  # destination search
        return httpx.Response(200, json={"places": places}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(providers, "_google_request_windows", providers.defaultdict(providers.deque))
    await GoogleMapsProvider("test-key").plan_trip("A", "B", 400, "medium", "08:10", "balanced")
    empty_points = set(corridor_points[1:])
    assert {lat for kind, lat in backfills if kind == "gas_station"} == empty_points
    assert {lat for kind, lat in backfills if kind == "restaurant"} == empty_points


async def _corridor_search_count(monkeypatch, distance_m: int) -> int:
    polyline = _encode_polyline([(1.30 + i * 0.05, 103.80) for i in range(40)])
    corridor = []

    async def fake_post(self, url, **kwargs):
        if url == providers.GOOGLE_ROUTES_URL:
            body = {"routes": [{"distanceMeters": distance_m, "duration": "21600s", "staticDuration": "21000s", "polyline": {"encodedPolyline": polyline}}]}
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))
        payload = kwargs["json"]
        if len(payload["includedTypes"]) > 1 and payload["locationRestriction"]["circle"]["radius"] == providers.ROUTE_MODE_CONFIG["balanced"]["corridor_radius"]:
            corridor.append(payload)
        lat = payload["locationRestriction"]["circle"]["center"]["latitude"]
        return httpx.Response(200, json={"places": [_place(f"gas-{lat}", "gas_station", lat), _place(f"food-{lat}", "restaurant", lat)]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(providers, "_google_request_windows", providers.defaultdict(providers.deque))
    await GoogleMapsProvider("test-key").plan_trip("A", "B", 400, "medium", "08:10", "balanced")
    return len(corridor)


async def test_long_routes_search_more_corridor_points(monkeypatch):
    # About one point every 120 km: 600 km gets 4 along-route searches instead of the mode's 3.
    assert await _corridor_search_count(monkeypatch, 600_000) == 4


async def test_short_routes_keep_the_mode_sample_count(monkeypatch):
    assert await _corridor_search_count(monkeypatch, 167_000) == 3


async def test_corridor_points_are_capped(monkeypatch):
    assert await _corridor_search_count(monkeypatch, 3_000_000) == providers.MAX_CORRIDOR_SAMPLES - 2
