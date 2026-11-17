from backend.okf import render_profile_okf
from backend.user_context import build_user_context


def _event(event_id, event_type, data, created_at):
    return {"id": event_id, "event_type": event_type, "data": data, "created_at": created_at}


def _signal(context, name):
    return next(item for item in context["learned_signals"] if item["signal"] == name)


def test_profile_only_signal_is_labelled_profile():
    s = _signal(build_user_context({"preferences": ["local-gems"]}), "local_food")
    assert s["source"] == "profile" and s["evidence_count"] == 0 and s["confidence"] == 0.55
    assert s["label"] == "local food"


def test_behaviour_signal_counts_evidence():
    events = [_event("1", "chatbot_search", {"query": "quiet cafe"}, "2026-11-01T00:00:00+00:00")]
    s = build_user_context({}, events=events)["learned_signals"][0]
    assert (s["signal"], s["source"], s["evidence_count"]) == ("quiet_low_crowd_stops", "behaviour", 1)


def test_both_sources():
    events = [_event("1", "chatbot_search", {"query": "local food"}, "2026-11-01T00:00:00+00:00")]
    s = _signal(build_user_context({"preferences": ["local-gems"]}, events=events), "local_food")
    assert s["source"] == "both"


def test_dismissed_behaviour_signal_is_excluded():
    events = [
        _event("1", "chatbot_search", {"query": "quiet cafe"}, "2026-11-01T00:00:00+00:00"),
        _event("2", "signal_dismissed", {"signal": "quiet_low_crowd_stops"}, "2026-11-02T00:00:00+00:00"),
    ]
    assert "quiet_low_crowd_stops" not in build_user_context({}, events=events)["learned_preferences"]


def test_newer_evidence_after_dismissal_relearns():
    events = [
        _event("1", "chatbot_search", {"query": "quiet cafe"}, "2026-11-01T00:00:00+00:00"),
        _event("2", "signal_dismissed", {"signal": "quiet_low_crowd_stops"}, "2026-11-02T00:00:00+00:00"),
        _event("3", "chatbot_search", {"query": "low crowd lookout"}, "2026-11-03T00:00:00+00:00"),
    ]
    s = _signal(build_user_context({}, events=events), "quiet_low_crowd_stops")
    assert s["source"] == "behaviour" and s["evidence_count"] == 1


def test_dismissal_keeps_profile_source():
    events = [_event("2", "signal_dismissed", {"signal": "local_food"}, "2026-11-02T00:00:00+00:00")]
    s = _signal(build_user_context({"preferences": ["local-gems"]}, events=events), "local_food")
    assert s["source"] == "profile"


def test_dismissal_event_is_not_evidence():
    events = [_event("2", "signal_dismissed", {"signal": "scenic_views", "reason": "scenic view"}, "2026-11-02T00:00:00+00:00")]
    assert build_user_context({}, events=events)["learned_signals"] == []


def test_okf_renders_source():
    doc = render_profile_okf(build_user_context({"preferences": ["local-gems"]}), timestamp="t")
    assert "local_food (from profile; confidence 0.55; evidence 0)" in doc
