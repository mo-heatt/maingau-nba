"""The Overview page's numbers come from the real mock data, and our engine must show zero violations."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def overview(tmp_path_factory):
    if not (ROOT / "data" / "maingau_nba_mockdata.xlsx").exists():
        pytest.skip("Mock data not present: put maingau_nba_mockdata.xlsx in data/")
    os.environ["NBA_DB_PATH"] = str(tmp_path_factory.mktemp("db") / "overview.sqlite")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        return client.get("/api/overview").json()


def test_our_engine_has_no_violations(overview):
    assert overview["violations"] == 0
    assert overview["summary"]["customers"] == 750


def test_legacy_audit_counts_from_source(overview):
    L = overview["legacy"]
    assert L["actions"] == 2270 and L["consent_not_checked"] == 333
    assert 0 < L["unchecked_and_no_consent"] <= L["consent_not_checked"]
    assert 0 < L["app_push_without_app"] <= L["app_push"]
    assert L["agent_dismissed_upset"] <= L["agent_dismissed"] <= L["agent_suggestions"]


def test_cases_are_real_customers(overview):
    assert overview["cases"] == {"service": "MG-100004", "sale": "MG-100068"}
