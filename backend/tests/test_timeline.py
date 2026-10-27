"""One customer timeline across every source system."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    if not (ROOT / "data" / "maingau_nba_mockdata.xlsx").exists():
        pytest.skip("Mock data not present: put maingau_nba_mockdata.xlsx in data/")
    os.environ["NBA_DB_PATH"] = str(tmp_path_factory.mktemp("db") / "timeline.sqlite")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_runs_from_first_contract_to_today(client):
    t = client.get("/api/customers/MG-100004/timeline").json()
    at = [e["at"] for e in t["entries"]]
    assert at == sorted(at, reverse=True)
    assert t["entries"][-1]["source"] == "crm" and t["since"].startswith("2019")
    sources = {s["key"] for s in t["sources"]}
    assert {"crm", "contract", "svc", "nba", "consent", "live"} <= sources


def test_live_events_are_deduplicated_and_flagged(client):
    t = client.get("/api/customers/MG-100004/timeline").json()
    dunning = [e for e in t["entries"] if e["title"] == "Dunning level changed"]
    assert len(dunning) == 1 and dunning[0]["flag"] == "bad"


def test_future_dates_are_marked_upcoming(client):
    t = client.get("/api/customers/MG-100068/timeline").json()
    guarantee = next(e for e in t["entries"] if e["title"].startswith("Price guarantee"))
    assert guarantee["upcoming"] and guarantee["at"].startswith("2026-10-08")


def test_unknown_customer_is_404(client):
    assert client.get("/api/customers/MG-999999/timeline").status_code == 404
