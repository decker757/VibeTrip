import asyncio
import concurrent.futures
import sys
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """Keep every test offline and write OKF files to a temp dir."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setenv("VIBETRIP_LIVE_MAPS_ENABLED", "false")
    monkeypatch.setenv("VIBETRIP_OKF_DIR", str(tmp_path))
    if "backend.okf" in sys.modules:
        monkeypatch.setattr("backend.okf.OKF_ROOT", tmp_path)


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


@pytest.fixture
def demo_state():
    """Factory returning a planner state built from the demo maps provider."""

    def build(route_mode: str = "balanced", end_time: str = "18:00") -> dict:
        from backend.providers import DemoMapsProvider

        result = _run(DemoMapsProvider().plan_trip("A", "B", 400, "medium", "08:10", route_mode))
        return {
            "start": "A",
            "destination": "B",
            "budget_per_person": 400,
            "start_date": "2026-11-20",
            "start_time": "08:10",
            "end_time": end_time,
            "adventure_level": 70,
            "route_mode": route_mode,
            "route": result.route,
            "candidate_places": result.candidates,
        }

    return build


@pytest.fixture
def auth_client():
    from backend.auth import get_current_user
    from backend.main import app

    user = {"id": f"test-{uuid.uuid4().hex[:8]}", "display_name": "Tester", "home_base": "Singapore", "email": "t@example.com"}
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
