"""Importing one customer: dry run stores nothing, a real import appends rows and the engine picks the customer up."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NEW = {"customer": {"customer_id": "MG-900001", "customer_type": "B2C", "customer_since": "2026-09-15", "birth_year": 1990,
                    "postal_code_prefix": "603", "city": "Frankfurt", "household_size": 2, "portal_account": True,
                    "app_installed": False, "preferred_contact_language": "de"},
       "consents": {"newsletter_email": "granted", "marketing_phone": "not_given"}}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    if not (ROOT / "data" / "maingau_nba_mockdata.xlsx").exists():
        pytest.skip("Mock data not present: put maingau_nba_mockdata.xlsx in data/")
    os.environ["NBA_DB_PATH"] = str(tmp_path_factory.mktemp("db") / "import.sqlite")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_dry_run_stores_nothing(client):
    r = client.post("/api/customers/import", json={**NEW, "dry_run": True})
    assert r.status_code == 200 and r.json()["stored"] is False
    assert r.json()["consents"]["marketing_sms"] == "not_given"  # missing consent is never assumed
    assert client.get("/api/customers/MG-900001").status_code == 404


def test_import_adds_customer_and_audit(client):
    r = client.post("/api/customers/import", json=NEW)
    assert r.status_code == 200 and r.json()["stored"] is True
    c = client.get("/api/customers/MG-900001").json()
    assert c["city"] == "Frankfurt" and c["consent"]["newsletter_email"]["status"] == "granted"
    assert client.get("/api/health").json()["customers"] == 751
    from app import database as db
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM audit WHERE kind='customer_imported' AND customer_id='MG-900001'").fetchone()[0] == 1


def test_duplicate_and_invalid_are_rejected(client):
    assert client.post("/api/customers/import", json=NEW).status_code == 409
    bad = {"customer": {**NEW["customer"], "customer_id": "MG-12", "postal_code_prefix": "60"}, "consents": {"fax": "granted"}}
    r = client.post("/api/customers/import", json=bad)
    assert r.status_code == 422 and "customer_id" in r.json()["detail"] and "fax" in r.json()["detail"]
