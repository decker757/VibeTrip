from backend.providers import _candidate_in_route_segment, _score_place


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
