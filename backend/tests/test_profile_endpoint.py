def test_profile_okf_returns_learned_signals(auth_client):
    body = auth_client.post("/profiles/okf", json={"preferences": ["local-gems"]}).json()
    assert {"signal": "local_food", "source": "profile"}.items() <= body["learned_signals"][0].items()


def test_dismiss_then_reload_hides_signal(auth_client):
    auth_client.post("/profiles/events", json={"event_type": "chatbot_search", "data": {"query": "quiet cafe"}})
    before = auth_client.post("/profiles/okf", json={"preferences": []}).json()
    assert any(s["signal"] == "quiet_low_crowd_stops" for s in before["learned_signals"])
    auth_client.post("/profiles/events", json={"event_type": "signal_dismissed", "data": {"signal": "quiet_low_crowd_stops"}})
    after = auth_client.post("/profiles/okf", json={"preferences": []}).json()
    assert all(s["signal"] != "quiet_low_crowd_stops" for s in after["learned_signals"])
