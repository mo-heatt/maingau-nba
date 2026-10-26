"""Case Radar flags stuck service customers with a one-line reason each."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def radar(tmp_path_factory):
    if not (ROOT / "data" / "maingau_nba_mockdata.xlsx").exists():
        pytest.skip("Mock data not present: put maingau_nba_mockdata.xlsx in data/")
    os.environ["NBA_DB_PATH"] = str(tmp_path_factory.mktemp("db") / "radar.sqlite")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        return client.get("/api/radar").json()


def test_every_flag_has_a_reason_and_an_open_complaint(radar):
    assert radar["cards"]
    for c in radar["cards"]:
        assert c["why"] and any(t["status"] == "open" for t in c["timeline"])


def test_our_real_case_is_flagged_first(radar):
    first = radar["cards"][0]
    assert first["customer_id"] == "MG-100004"
    assert len(first["why"]) == 2 and first["dunning_level"] == 3
    assert first["sales_while_waiting"] >= 1
    assert first["actions"][0]["id"] == "pause_reminders"
