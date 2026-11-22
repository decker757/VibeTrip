def test_health(auth_client):
    assert auth_client.get("/health").status_code == 200


def test_demo_state_builds(demo_state):
    state = demo_state()
    assert state["route"] and state["candidate_places"]


def test_destination_suggestions_carry_their_visit_length(auth_client):
    plan = auth_client.post("/trips/plan", json={"start": "Singapore", "destination": "KL", "start_date": "2026-11-20"}).json()
    destination = next(place for place in plan["candidate_places"] if place.get("recommendation_scope") == "destination")
    assert destination["visit_minutes"] == 90  # Tourist attraction: not food
