from __future__ import annotations

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEPHONE_LIVE", "0")
    from fastapi.testclient import TestClient

    import api.main as m

    return TestClient(m.app)


def test_health_and_live_disabled(client):
    assert client.get("/api/health").json()["ok"] is True
    st = client.get("/api/live/status").json()
    assert st["enabled"] is False and "telephone" in st["presets"]
    r = client.post(
        "/api/live", json={"image": "street_fixture_01", "preset": "telephone", "generations": 2}
    )
    assert r.status_code == 403
    assert client.get("/api/chains/nope").status_code == 404
    assert client.post("/api/live", json={"image": "x", "generations": 99}).status_code == 422
