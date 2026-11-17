from pathlib import Path

from backend.okf import OKFProfileExporter


def _record_writes(monkeypatch) -> list:
    writes = []
    original = Path.write_text

    def recording_write(self, *args, **kwargs):
        writes.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", recording_write)
    return writes


def test_second_export_with_same_inputs_skips_write(monkeypatch):
    writes = _record_writes(monkeypatch)
    exporter = OKFProfileExporter()
    first = exporter.export({"preferences": []}, owner_id="u1")
    second = exporter.export({"preferences": []}, owner_id="u1")
    assert len(writes) == 1 and second["document"] == first["document"]


def test_new_event_invalidates_cache(monkeypatch):
    writes = _record_writes(monkeypatch)
    exporter = OKFProfileExporter()
    exporter.export({"preferences": []}, owner_id="u1")
    event = {"id": "e1", "event_type": "chatbot_search", "data": {"query": "quiet cafe"}, "created_at": "2026-11-01T00:00:00+00:00"}
    result = exporter.export({"preferences": []}, owner_id="u1", events=[event])
    assert len(writes) == 2 and "quiet_low_crowd_stops" in result["document"]


def test_cache_is_per_owner(monkeypatch):
    writes = _record_writes(monkeypatch)
    exporter = OKFProfileExporter()
    exporter.export({"preferences": []}, owner_id="u1")
    exporter.export({"preferences": []}, owner_id="u2")
    assert len(writes) == 2
