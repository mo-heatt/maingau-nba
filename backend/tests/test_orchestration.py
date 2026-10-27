"""The marketing dashboard adds up to the engine's decisions, and the what-if preview never saves anything."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    if not (ROOT / "data" / "maingau_nba_mockdata.xlsx").exists():
        pytest.skip("Mock data not present: put maingau_nba_mockdata.xlsx in data/")
    os.environ["NBA_DB_PATH"] = str(tmp_path_factory.mktemp("db") / "orchestration.sqlite")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def m(client):
    return client.get("/api/marketing").json()


def test_segments_cover_every_customer(m):
    for cut, rows in m["segments"].items():
        assert sum(r["customers"] for r in rows) == m["customers"], cut
        assert round(sum(r["expected_gain_eur"] for r in rows), 2) == pytest.approx(m["expected_gain_eur"], abs=0.05), cut


def test_queue_is_every_contactable_action(m):
    assert len(m["queue"]) == m["offers"] + m["service_fixes"] - m["held_out"]
    assert all(not r["decision"]["control_group"] for r in m["queue"])
    gains = [r["decision"]["expected_gain_eur"] for r in m["queue"]]
    assert gains == sorted(gains, reverse=True)
    assert sum(m["funnel"].values()) == m["offers"] + m["service_fixes"]


def test_left_alone_adds_up(m):
    assert sum(r["customers"] for r in m["left_alone"]) == m["no_contact"]


def test_preview_does_not_save(client, m):
    settings = client.get("/api/settings").json()
    draft = {**settings, "channels_off": ["outbound_call", "sms"], "contact_cap_30d": 1}
    p = client.post("/api/marketing/preview", json=draft).json()
    assert p["before"]["expected_gain_eur"] == m["expected_gain_eur"]
    assert not {"outbound_call", "sms"} & set(p["after"]["channels"])
    assert p["after"]["wait"] >= p["before"]["wait"]
    assert client.get("/api/settings").json()["version"] == settings["version"]


def test_preview_rejects_unknown_offer(client):
    settings = client.get("/api/settings").json()
    assert client.post("/api/marketing/preview", json={**settings, "offers_off": ["P-NOPE"]}).status_code == 409
