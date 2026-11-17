from backend.storage import OWNER_ID, TripRepository


class EmptyCursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        pass

    def fetchall(self):
        return []


class EmptyConnection:
    def cursor(self):
        return EmptyCursor()

    def commit(self):
        pass

    def close(self):
        pass


def test_memory_trip_saved_during_cooldown_listed_after_recovery(monkeypatch):
    now = [0.0]
    up = [False]

    def fake_connect(url, connect_timeout):
        if not up[0]:
            raise OSError("down")
        return EmptyConnection()

    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setattr("backend.db._psycopg_connect", fake_connect)
    repo = TripRepository()
    repo._db._clock = lambda: now[0]
    saved = repo.save({"id": "t1", "title": "Outage trip", "start": "A", "destination": "B"})
    up[0] = True
    now[0] = 31
    assert [trip["id"] for trip in repo.list_saved(OWNER_ID)] == [saved["id"]]
