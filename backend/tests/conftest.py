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
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("VIBETRIP_LIVE_MAPS_ENABLED", "false")
    monkeypatch.setenv("VIBETRIP_OKF_DIR", str(tmp_path))
    if "backend.okf" in sys.modules:
        monkeypatch.setattr("backend.okf.OKF_ROOT", tmp_path)


@pytest.fixture
def demo_state():
    """Factory returning a planner state built from the demo maps provider."""
    from backend.tests.planner_helpers import build_demo_state

    def build(route_mode: str = "balanced", end_time: str = "18:00") -> dict:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return build_demo_state(route_mode, end_time)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(build_demo_state, route_mode, end_time).result()

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
