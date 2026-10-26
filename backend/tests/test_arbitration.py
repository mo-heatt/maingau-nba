"""The arbitration rule table: what the engine does once every candidate is scored."""
from app.engine.arbitration import arbitrate


def cand(offer="P-MO-01", dclv=10.0, blocked=None, type="cross_sell"):
    return {"offer": offer, "name": offer, "type": type, "dclv": dclv, "blocked": blocked or [],
            "channel": "email", "channel_label": "Marketing e-mail", "p": 0.1, "why": "test"}


def sc(candidates, case=()):
    return {"service_case": list(case), "candidates": candidates}


def test_cancellation_always_goes_to_a_human(make_state, settings):
    s = make_state(signals={"cancellation_pending": {"value": True, "class": "contract"}})
    d = arbitrate(s, sc([cand(dclv=999.0)]), settings)
    assert d["action"] == "human_review"


def test_service_case_prefers_the_fix_over_a_better_sale(make_state, settings):
    candidates = [cand("P-MO-01", dclv=100.0), cand("P-SV-01", dclv=40.0, type="service")]
    d = arbitrate(make_state(), sc(candidates, case=["open complaint"]), settings)
    assert d["action"] == "offer"
    assert d["pick"]["offer"] == "P-SV-01"


def test_service_case_without_a_worthwhile_fix_means_no_contact(make_state, settings):
    d = arbitrate(make_state(), sc([cand("P-MO-01", dclv=100.0)], case=["open complaint"]), settings)
    assert d["action"] == "none"


def test_below_minimum_gain_means_no_contact(make_state, settings):
    settings["min_dclv_eur"] = 5.0
    d = arbitrate(make_state(), sc([cand(dclv=4.99)]), settings)
    assert d["action"] == "none"
    assert "not worth" in d["reason"]


def test_no_candidates_means_no_contact(make_state, settings):
    assert arbitrate(make_state(), sc([]), settings)["action"] == "none"


def test_blocked_candidates_are_ignored(make_state, settings):
    blocked = cand("P-MO-01", dclv=500.0, blocked=["Exclusion: open complaint"])
    d = arbitrate(make_state(), sc([blocked]), settings)
    assert d["action"] == "none"


def test_contact_limit_means_wait(make_state, settings):
    s = make_state(contacts_30d=3)  # SETTINGS contact_cap_30d = 3
    d = arbitrate(s, sc([cand(dclv=50.0)]), settings)
    assert d["action"] == "wait"
    assert d["pick"]["offer"] == "P-MO-01"


def test_higher_expected_gain_wins(make_state, settings):
    candidates = [cand("P-SH-01", dclv=30.0), cand("P-IN-01", dclv=80.0)]
    d = arbitrate(make_state(), sc(candidates), settings)
    assert d["action"] == "offer"
    assert d["pick"]["offer"] == "P-IN-01"
    assert "+€80" in d["reason"]


def test_marketing_priorities_reweight_the_ranking(make_state, settings):
    candidates = [cand("P-IN-01", dclv=100.0), cand("P-SH-01", dclv=150.0)]
    settings["priorities"] = {"P-SH-01": "low"}
    d = arbitrate(make_state(), sc(candidates), settings)
    assert d["pick"]["offer"] == "P-IN-01"  # 150 * 0.5 < 100
    settings["priorities"] = {"P-SH-01": "high"}
    d = arbitrate(make_state(), sc(candidates), settings)
    assert d["pick"]["offer"] == "P-SH-01"  # 150 * 1.5 > 100
