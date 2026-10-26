"""Signal usability (consent classes) and offer targeting rules."""
from app.engine.signals import candidate_offers, has, service_case, usable


def sig(cls="contract", value=True):
    return {"value": value, "class": cls}


def test_behavioural_signals_need_profiling_consent(make_state):
    s = make_state(signals={"heat_pump_usage": sig("behavioural", 500)})
    s["consent"]["profiling_analytics"] = {"status": "not_given"}
    assert not usable(s, "heat_pump_usage")
    assert "P-EN-03" not in candidate_offers(s)[0]
    s["consent"]["profiling_analytics"] = {"status": "granted"}
    assert usable(s, "heat_pump_usage")
    assert "P-EN-03" in candidate_offers(s)[0]


def test_contract_signals_are_usable_without_profiling_consent(make_state):
    s = make_state(signals={"guarantee_ending": sig(value="2026-11-01")},
                   consent={"profiling_analytics": {"status": "not_given"}})
    assert usable(s, "guarantee_ending")
    cands, _ = candidate_offers(s)
    assert cands["P-EN-02"][0] == "strong"


def test_customer_without_any_products_gets_no_offers(make_state):
    assert candidate_offers(make_state()) == ({}, {})


def test_electricity_customer_gets_adjacent_cross_sell(make_state):
    cands, _ = candidate_offers(make_state(holds={"electricity"}))
    assert {"P-MO-01", "P-IN-01", "P-SH-01"} <= set(cands)
    assert all(cands[k][0] == "weak" for k in ("P-MO-01", "P-IN-01", "P-SH-01"))


def test_no_offer_for_products_the_customer_already_holds(make_state):
    cands, _ = candidate_offers(make_state(holds={"electricity", "mobile"}))
    assert "P-MO-01" not in cands
    assert "P-EN-01" not in cands


def test_energy_offer_only_without_electricity(make_state):
    cands, _ = candidate_offers(make_state(holds={"gas"}))
    assert "P-EN-01" in cands
    cands2, _ = candidate_offers(make_state(holds={"gas", "electricity"}))
    assert "P-EN-01" not in cands2


def test_intent_from_newsletter_clicks_is_behavioural(make_state):
    s = make_state(signals={"clicked_heat_pump": sig("behavioural", 1)},
                   consent={"profiling_analytics": {"status": "not_given"}})
    assert candidate_offers(s)[1] == {}
    s["consent"]["profiling_analytics"] = {"status": "granted"}
    _, intent = candidate_offers(s)
    assert set(intent) == {"P-EN-03", "P-SL-01"}


def test_cart_intent_requires_profiling_consent(make_state):
    s = make_state(cart_intent={"P-SH-04": "abandoned cart: Smart Plug"},
                   consent={"profiling_analytics": {"status": "not_given"}})
    assert candidate_offers(s)[1] == {}


def test_service_case_rules(make_state):
    assert service_case(make_state()) == []
    assert service_case(make_state(signals={"open_complaint": sig(value="T-1")})) == ["open complaint"]
    assert service_case(make_state(signals={"dunning_level": sig(value=1)})) == ["dunning level 1"]
    assert "cancellation received" in service_case(make_state(signals={"cancellation_pending": sig()}))


def test_has_checks_the_signal_presence(make_state):
    s = make_state(signals={"open_complaint": sig(value="T-1")})
    assert has(s, "open_complaint")
    assert not has(s, "failed_charges")
