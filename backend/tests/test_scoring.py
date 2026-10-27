"""dCLV scoring: channel gating, churn composition and the scoring formula."""
import pytest

from app.engine.scoring import channel_options, churn_parts, current_churn, score_customer


def test_every_channel_needs_its_consent(make_state, P, A):
    s = make_state(consent={}, portal_account=False, app_installed=False)
    ch = {c["channel"]: c for c in channel_options(s, A, P)}
    for key in ("email", "sms", "outbound_call", "portal_popup", "app_push", "newsletter_email"):
        assert not ch[key]["allowed"], key
        assert "no consent" in ch[key]["why_not"]


def test_newsletter_needs_double_opt_in(make_state, P, A):
    s = make_state(consent={"newsletter_email": {"status": "granted", "doi": None}})
    ch = {c["channel"]: c for c in channel_options(s, A, P)}
    assert "double opt-in" in ch["newsletter_email"]["why_not"]


def test_portal_popup_needs_a_portal_account(make_state, P, A):
    s = make_state(portal_account=False)
    ch = {c["channel"]: c for c in channel_options(s, A, P)}
    assert "portal account" in ch["portal_popup"]["why_not"]


def test_churn_parts_map_the_drivers_from_the_clv_model(make_state, P):
    s = make_state()
    s["value"]["churn_drivers"] = ["price guarantee ends in 90 days", "open complaint"]
    parts = churn_parts(s, P)
    assert parts["price_guarantee_ends_90d"] == P["price_guarantee_ends_90d"]
    assert parts["open_complaint"] == P["open_complaint"]


def test_live_events_add_churn_drivers_the_monthly_model_has_not_seen(make_state, P):
    s = make_state(signals={"open_complaint": {"value": "T-1", "class": "contract"}})
    assert churn_parts(s, P)["open_complaint"] == P["open_complaint"]


def test_current_churn_adds_live_drivers(make_state, P):
    s = make_state(live_churn_add={"open_complaint": 0.12})
    assert current_churn(s, P) == pytest.approx(0.22)


def test_cancellation_sets_a_churn_floor(make_state, P):
    s = make_state(live_churn_add={"open_complaint": 0.12})
    s["signals"]["cancellation_pending"] = {"value": True, "class": "contract"}
    assert current_churn(s, P) == pytest.approx(P["cancellation_pending"])


def test_churn_is_capped_at_95_percent(make_state, P):
    s = make_state(live_churn_add={"dunning": 0.30})
    s["value"]["churn"] = 0.90
    assert current_churn(s, P) == pytest.approx(0.95)


def test_candidates_are_sorted_by_expected_gain(make_state, P, A, catalog, settings):
    sc = score_customer(make_state(holds={"electricity"}), {}, P, A, catalog, 0.43, settings)
    assert sc["candidates"]
    dclvs = [c["dclv"] for c in sc["candidates"]]
    assert dclvs == sorted(dclvs, reverse=True)


def test_p_is_always_between_0_and_60_percent(make_state, P, A, catalog, settings):
    sc = score_customer(make_state(holds={"electricity"}), {}, P, A, catalog, 0.43, settings)
    for c in sc["candidates"]:
        assert 0 < c["p"] <= 0.6
        assert 0 < c["p_base"]


def test_chosen_channel_is_the_best_one(make_state, P, A, catalog, settings):
    sc = score_customer(make_state(holds={"electricity"}), {}, P, A, catalog, 0.43, settings)
    for c in sc["candidates"]:
        if c["per_channel"]:
            assert c["dclv"] == pytest.approx(max(x["dclv"] for x in c["per_channel"]))


def test_dclv_follows_the_published_formula(make_state, P, A, catalog, settings):
    # dCLV = p(accept)*(CLV accept - CLV now) + (1-p)*(CLV reject - CLV now) - contact cost
    costs = {"portal_popup": P["contact_cost_popup_eur"], "app_push": P["contact_cost_popup_eur"],
             "newsletter_email": P["contact_cost_email_eur"], "email": P["contact_cost_email_eur"],
             "sms": P["contact_cost_sms_eur"], "outbound_call": P["contact_cost_call_eur"]}
    sc = score_customer(make_state(holds={"electricity"}), {}, P, A, catalog, 0.43, settings)
    c = next(c for c in sc["candidates"] if c["offer"] == "P-MO-01")
    expected = (c["p"] * (c["clv_accept"] - sc["clv_now"])
                + (1 - c["p"]) * (c["clv_reject"] - sc["clv_now"])
                - costs[c["channel"]])
    assert c["dclv"] == pytest.approx(expected, abs=0.02)


def test_offers_off_removes_candidates(make_state, P, A, catalog, settings):
    settings["offers_off"] = ["P-MO-01", "P-IN-01", "P-SH-01"]
    sc = score_customer(make_state(holds={"electricity"}), {}, P, A, catalog, 0.43, settings)
    assert sc["candidates"] == []


def test_disabled_channels_are_not_scored(make_state, P, A, catalog, settings):
    settings["channels_off"] = ["portal_popup", "app_push", "newsletter_email", "email", "sms", "outbound_call"]
    sc = score_customer(make_state(holds={"electricity"}), {}, P, A, catalog, 0.43, settings)
    assert sc["candidates"]
    for c in sc["candidates"]:
        assert c["per_channel"] == []
        assert any("No marketing channel" in b for b in c["blocked"])


def test_open_complaint_blocks_sales_and_offers_the_service_fix(make_state, P, A, catalog, settings):
    s = make_state(holds={"electricity"}, signals={"open_complaint": {"value": "T-1", "class": "contract"}})
    s["value"]["churn_drivers"] = ["open complaint"]
    sc = score_customer(s, {}, P, A, catalog, 0.43, settings)
    svc = [c for c in sc["candidates"] if c["offer"] == "P-SV-01"]
    sales = [c for c in sc["candidates"] if c["offer"] != "P-SV-01"]
    assert svc and svc[0]["channel"] == "agent_callback"
    assert svc[0]["p"] == pytest.approx(0.43)  # p = first-contact resolution rate
    for c in sales:
        assert any("Exclusion" in b for b in c["blocked"])


def test_no_service_fix_when_cancellation_is_pending(make_state, P, A, catalog, settings):
    s = make_state(signals={"open_complaint": {"value": "T-1", "class": "contract"},
                            "cancellation_pending": {"value": True, "class": "contract"}})
    sc = score_customer(s, {}, P, A, catalog, 0.43, settings)
    assert all(c["offer"] != "P-SV-01" for c in sc["candidates"])


def test_personal_marketing_requires_profiling_consent(make_state, P, A, catalog, settings):
    s = make_state(holds={"electricity"})
    s["consent"]["profiling_analytics"] = {"status": "not_given"}
    sc = score_customer(s, {}, P, A, catalog, 0.43, settings)
    assert sc["candidates"]
    for c in sc["candidates"]:
        assert any("Profiling consent" in b for b in c["blocked"])


def test_acceptance_probability_is_capped_at_60_percent(make_state, P, A, catalog, settings):
    s = make_state(holds={"electricity"},
                   signals={"guarantee_ending": {"value": "2026-11-01", "class": "contract"}})
    a = {**A, "offer_rate": {**A["offer_rate"], "P-EN-02": 0.5}}  # 0.5 * strong lift 2.0 = 1.0
    sc = score_customer(s, {}, P, a, catalog, 0.43, settings)
    c = next(c for c in sc["candidates"] if c["offer"] == "P-EN-02")
    assert c["p_base"] == pytest.approx(1.0)
    assert c["p"] == pytest.approx(0.6)


def test_unapproved_template_blocks_the_offer(make_state, P, A, catalog, settings):
    settings["content_approvals"] = {"P-MO-01": {"du": False}}
    sc = score_customer(make_state(holds={"electricity"}, tone="du"), {}, P, A, catalog, 0.43, settings)
    c = next(c for c in sc["candidates"] if c["offer"] == "P-MO-01")
    assert any("not approved" in b for b in c["blocked"])


def test_portal_popup_needs_regular_logins():
    """Team rule: a portal pop-up only counts as strong for customers with 3+ logins in 90 days."""
    from app.engine.scoring import channel_options
    from app.engine.constants import PORTAL_REGULAR_LOGINS_90D
    def factor(sessions):
        s = {"consent": {k: {"status": "granted", "doi": "2026-01-01"} for k in
                         ["profiling_analytics", "portal_app_personalisation", "newsletter_email", "marketing_email", "marketing_sms", "marketing_phone"]},
             "portal_account": True, "app_installed": True, "portal_sessions_90d": sessions,
             "email_engagement": {"delivered": 0, "human_opens": 0}}
        P = {"contact_cost_popup_eur": 0, "contact_cost_email_eur": 0.01, "contact_cost_sms_eur": 0.08, "contact_cost_call_eur": 6}
        A = {"channel_factor": {}}
        return next(c["factor"] for c in channel_options(s, A, P) if c["channel"] == "portal_popup")
    assert factor(PORTAL_REGULAR_LOGINS_90D) == 1.3
    assert factor(1) == 0.6 and factor(0) == 0.6


def test_portal_login_event_counts_toward_popup_rule():
    from app.engine.events import apply_event
    s = {"portal_sessions_90d": 2, "signals": {}, "evidence": {}}
    note = apply_event(s, {"event_type": "portal_login", "payload": {"client": "web"}}, {})
    assert s["portal_sessions_90d"] == 3 and "3 in 90 days" in note


def test_data_warning_below_limit_does_not_create_signal():
    from collections import defaultdict
    from app.engine.events import apply_event
    s = {"signals": {}, "evidence": defaultdict(list)}
    note = apply_event(s, {"event_type": "mobile_data_threshold", "payload": {"threshold_pct": 80}}, {})
    assert "data_limit_reached" not in s["signals"] and "warning only" in note
