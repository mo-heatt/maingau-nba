"""Compliance invariants, checked end-to-end on every customer of the real mock data.

These are the automated version of the self-check promised in the README:
consent and exclusion violations must be exactly zero, for all 750 customers.
Skips gracefully when the mock data is not present.
"""
import itertools

import pytest

from app.ingestion import load_tables
from app.engine.arbitration import arbitrate
from app.engine.constants import CHANNELS, SETTINGS
from app.engine.scoring import acceptance_model, params, score_customer
from app.engine.state import build_state
from app.engine.templates import TEMPLATES
from app.service import control


@pytest.fixture(scope="session")
def tables(source_db):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("NBA_DB_PATH", str(source_db))
        return load_tables()


@pytest.fixture(scope="session")
def world(tables):
    X, quality = tables
    P = params(X)
    A = acceptance_model(X)
    catalog = X["product_catalog"].set_index("product_id")
    comp = X["service_interactions"]
    comp = comp[(comp.category == "complaint") & (comp.status == "closed")]
    fcr = float(comp.first_contact_resolution.mean())
    state = build_state(X)
    return X, P, A, catalog, fcr, state


@pytest.fixture(scope="session")
def scored(world):
    X, P, A, catalog, fcr, state = world
    out = {}
    for cid, s in state.items():
        sc = score_customer(s, X, P, A, catalog, fcr, SETTINGS)
        out[cid] = (s, sc, arbitrate(s, sc, SETTINGS))
    return out


def test_every_customer_is_scored(scored):
    assert len(scored) > 100


def test_no_sales_to_customers_with_open_complaint_dunning_or_cancellation(scored):
    violations = []
    for cid, (s, sc, d) in scored.items():
        if d["action"] == "offer" and d["pick"]["type"] != "service" and sc["service_case"]:
            violations.append((cid, sc["service_case"]))
    assert violations == []


def test_chosen_channel_always_has_consent(scored):
    violations = []
    for cid, (s, sc, d) in scored.items():
        if d["action"] != "offer":
            continue
        channel = d["pick"]["channel"]
        if channel == "agent_callback":
            continue
        entry = next(c for c in sc["channels"] if c["channel"] == channel)
        if not entry["allowed"]:
            violations.append((cid, channel, entry["why_not"]))
    assert violations == []


def test_contact_cap_is_respected_for_sales_offers(scored):
    cap = SETTINGS["contact_cap_30d"]
    violations = []
    for cid, (s, sc, d) in scored.items():
        if d["action"] == "offer" and d["pick"]["type"] != "service" and s["contacts_30d"] >= cap:
            violations.append((cid, s["contacts_30d"]))
    assert violations == []


def test_no_contact_below_the_minimum_expected_gain(scored):
    floor = SETTINGS["min_dclv_eur"]
    violations = []
    for cid, (s, sc, d) in scored.items():
        if d["action"] == "offer" and d["pick"]["dclv"] <= floor:
            violations.append((cid, d["pick"]["dclv"]))
    assert violations == []


def test_acceptance_probability_stays_bounded(scored):
    violations = []
    for cid, (s, sc, d) in scored.items():
        for c in sc["candidates"]:
            if not 0 < c["p"] <= 0.6:
                violations.append((cid, c["offer"], c["p"]))
    assert violations == []


def test_chosen_channel_maximises_the_expected_gain(scored):
    violations = []
    for cid, (s, sc, d) in scored.items():
        c = d.get("pick")
        if d["action"] == "offer" and c and c["per_channel"]:
            best = max(x["dclv"] for x in c["per_channel"])
            if c["dclv"] < best - 0.01:
                violations.append((cid, c["offer"], c["dclv"], best))
    assert violations == []


def test_sales_candidates_are_explicitly_blocked_during_service_cases(scored):
    for cid, (s, sc, d) in scored.items():
        if not sc["service_case"]:
            continue
        for c in sc["candidates"]:
            if c["type"] != "service":
                assert any("Exclusion" in b for b in c["blocked"]), cid


def test_every_proposed_offer_has_approved_templates(scored):
    for cid, (s, sc, d) in scored.items():
        pick = d.get("pick")
        if d["action"] == "offer" and pick:
            assert pick["offer"] in TEMPLATES, cid


def test_candidates_are_sorted_by_expected_gain(scored):
    for cid, (s, sc, d) in scored.items():
        dclvs = [c["dclv"] for c in sc["candidates"]]
        assert dclvs == sorted(dclvs, reverse=True), cid


def test_control_group_is_deterministic_and_about_ten_percent(scored):
    ids = sorted(scored)
    assert all(control(cid) == control(cid) for cid in ids[:25])
    share = sum(1 for cid in ids if control(cid)) / len(ids)
    assert 0.04 <= share <= 0.16, share


def test_scoring_is_deterministic(world):
    X, P, A, catalog, fcr, state = world
    for cid in itertools.islice(sorted(state), 25):
        s = state[cid]
        a = score_customer(s, X, P, A, catalog, fcr, SETTINGS)
        b = score_customer(s, X, P, A, catalog, fcr, SETTINGS)
        assert a == b, cid
