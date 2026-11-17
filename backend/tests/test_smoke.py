def test_health(auth_client):
    assert auth_client.get("/health").status_code == 200


def test_demo_state_builds(demo_state):
    state = demo_state()
    assert state["route"] and state["candidate_places"]
