"""Shared fixtures for the engine tests.

The engine functions take plain dicts and DataFrames, so the unit tests feed
handcrafted minimal versions instead of the 1.8 MB mock workbook. The
compliance invariants in test_invariants.py run on the real data.
"""
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pandas as pd
import pytest

from app.engine.constants import SETTINGS

# data/ is gitignored, so the workbook is missing in CI: tests that need it must skip, not crash.
MOCKDATA = BACKEND.parent / "data" / "maingau_nba_mockdata.xlsx"


@pytest.fixture(scope="session")
def mockdata():
    if not MOCKDATA.exists():
        pytest.skip("Mock data not present: put maingau_nba_mockdata.xlsx in data/")
    return MOCKDATA


@pytest.fixture(scope="session")
def source_db(tmp_path_factory, mockdata):
    """A database imported from the workbook, as the app does at startup. Tests copy it, never write to it."""
    from app import database as db, newsletter
    from app.ingestion import import_sources
    path = tmp_path_factory.mktemp("source") / "nba.sqlite"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("NBA_DB_PATH", str(path))
        db.initialize(); newsletter.seed(); import_sources()
    return path


@pytest.fixture(scope="session")
def P():
    """Value assumptions, same keys as the clv_method sheet of the mock data."""
    return {
        "contact_cost_popup_eur": 0.10,
        "contact_cost_email_eur": 0.15,
        "contact_cost_sms_eur": 0.07,
        "contact_cost_call_eur": 2.50,
        "price_guarantee_ends_90d": 0.06,
        "open_complaint": 0.08,
        "tickets_12m_ge2": 0.03,
        "csat_le2": 0.04,
        "dunning_ge2": 0.07,
        "failed_charges_30d_ge3": 0.05,
        "cancellation_pending": 0.60,
        "contact_during_service_case": 0.05,
        "service_resolution_cost_eur": 25.0,
    }


@pytest.fixture(scope="session")
def A():
    """Acceptance model in the shape acceptance_model() returns."""
    return {
        "global": 0.08,
        "channel_factor": {"email": 1.0, "newsletter_email": 1.2},
        "offer_rate": {"P-EN-02": 0.12, "P-MO-01": 0.08, "P-IN-01": 0.09, "P-SH-01": 0.07, "P-SH-04": 0.10},
        "uplift": [],
        "overall": {},
    }


@pytest.fixture(scope="session")
def catalog():
    rows = [
        {"product_id": "P-EN-02", "product_name": "StromGarant Preisgarantie", "business_line": "energy",
         "annual_margin_if_bought_eur": 40.0, "churn_effect_if_bought": -0.04, "action_type": "retention"},
        {"product_id": "P-MO-01", "product_name": "Mobil MVP", "business_line": "mobile",
         "annual_margin_if_bought_eur": 60.0, "churn_effect_if_bought": 0.0, "action_type": "cross_sell"},
        {"product_id": "P-IN-01", "product_name": "Internet DSL", "business_line": "internet",
         "annual_margin_if_bought_eur": 80.0, "churn_effect_if_bought": 0.0, "action_type": "cross_sell"},
        {"product_id": "P-SH-01", "product_name": "Balkonkraftwerk", "business_line": "shop",
         "annual_margin_if_bought_eur": 12.0, "churn_effect_if_bought": 0.0, "action_type": "one_off"},
        {"product_id": "P-SH-04", "product_name": "Smart Plug", "business_line": "shop",
         "annual_margin_if_bought_eur": 6.0, "churn_effect_if_bought": 0.0, "action_type": "one_off"},
        {"product_id": "P-SV-01", "product_name": "Proactive service fix", "business_line": "service",
         "annual_margin_if_bought_eur": 0.0, "churn_effect_if_bought": 0.0, "action_type": "service"},
    ]
    return pd.DataFrame(rows).set_index("product_id")


GRANTED_CONSENT = {
    "profiling_analytics": {"status": "granted", "updated_at": "2026-01-01", "source": "portal", "doi": None},
    "portal_app_personalisation": {"status": "granted", "updated_at": "2026-01-01", "source": "portal", "doi": None},
    "newsletter_email": {"status": "granted", "updated_at": "2026-01-01", "source": "doi", "doi": "2026-01-02"},
    "marketing_email": {"status": "granted", "updated_at": "2026-01-01", "source": "portal", "doi": None},
    "marketing_sms": {"status": "granted", "updated_at": "2026-01-01", "source": "portal", "doi": None},
    "marketing_phone": {"status": "granted", "updated_at": "2026-01-01", "source": "portal", "doi": None},
}


@pytest.fixture
def make_state():
    """A customer state with every consent granted and no signals yet."""

    def _make(**over):
        s = {
            "customer_id": "MG-TEST", "city": "Darmstadt", "customer_since": "2020-01-01",
            "birth_year": 1985, "household_size": 2, "portal_account": True, "app_installed": True,
            "language": "de", "consent": {k: dict(v) for k, v in GRANTED_CONSENT.items()},
            "value": {"annual_margin": 200.0, "cost_to_serve": 30.0, "service_cost": 10.0, "churn": 0.10,
                      "clv": 900.0, "clv_service_impact": -50.0, "churn_drivers": [], "lines": 1},
            "products": [], "holds": set(), "signals": {}, "evidence": defaultdict(list),
            "open_tickets": [], "recent_tickets": [], "texts": [],
            "failed_charges_30d": 0, "contacts_30d": 0, "portal_sessions_90d": 5,
            "email_engagement": {"delivered": 0, "human_opens": 0, "machine_opens": 0, "clicks": 0},
            "tone": "du", "tone_reason": "test", "tone_sample": None, "live_churn_add": {},
            "legacy_actions": [],
        }
        s.update(over)
        return s

    return _make


@pytest.fixture
def settings():
    """Fresh copy of the default settings per test (tests may mutate it)."""
    return dict(SETTINGS)
