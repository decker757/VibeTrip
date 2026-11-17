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
