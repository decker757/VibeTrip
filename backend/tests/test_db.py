from backend.db import PostgresConnector


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        pass


class FakeConnection:
    def cursor(self):
        return FakeCursor()

    def commit(self):
        pass

    def close(self):
        pass


def test_no_database_url_returns_none(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert PostgresConnector().connect() is None


def test_failure_then_recovery_after_cooldown(monkeypatch):
    now = [0.0]
    attempts = []

    def fake_connect(url, connect_timeout):
        attempts.append(now[0])
        if len(attempts) == 1:
            raise OSError("down")
        return FakeConnection()

    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setattr("backend.db._psycopg_connect", fake_connect)
    connector = PostgresConnector(cooldown_seconds=30, clock=lambda: now[0])
    assert connector.connect() is None
    now[0] = 10
    assert connector.connect() is None and len(attempts) == 1
    now[0] = 31
    assert connector.connect() is not None and len(attempts) == 2


def test_mark_failed_starts_cooldown_and_schema_ensured_once(monkeypatch):
    now = [0.0]
    attempts = []

    def fake_connect(url, connect_timeout):
        attempts.append(now[0])
        return FakeConnection()

    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setattr("backend.db._psycopg_connect", fake_connect)
    connector = PostgresConnector(cooldown_seconds=30, clock=lambda: now[0])
    assert connector.connect() is not None
    connector.mark_failed(RuntimeError("boom"))
    assert connector.connect() is None
    now[0] = 31
    assert connector.connect() is not None
