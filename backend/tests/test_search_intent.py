from backend.search_intent import PlaceSearchIntent, _deterministic_intent, _safe_llm_intent


def test_invented_locality_is_replaced_by_fallback():
    query = "a quiet cafe"
    decision = PlaceSearchIntent(maps_query="quiet cafe near Melaka", category="cafe", location_hint="melaka")
    assert _safe_llm_intent(decision, _deterministic_intent(query), query).location_hint is None


def test_explicit_locality_is_kept():
    query = "a quiet cafe near ipoh"
    decision = PlaceSearchIntent(maps_query="quiet cafe", category="cafe", location_hint="ipoh")
    parsed = _safe_llm_intent(decision, _deterministic_intent(query), query)
    assert parsed.location_hint == "ipoh" and "ipoh" in parsed.maps_query.lower()
