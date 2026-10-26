"""Numbers for the Overview page: what today's rule engine did, and a live compliance check of ours.

Everything is counted from the imported source tables, so the page never shows a hard-coded figure.
"""
import collections

import pandas as pd

from .engine.constants import CHANNELS
from .engine.signals import service_case

# Real customers used as worked examples on the Overview page.
CASES = {"service": "MG-100004", "sale": "MG-100068"}


def legacy_audit(X):
    """How the current rule engine (nba_action_history, Jun–Sep 2026) behaved."""
    h = X["nba_action_history"]
    cons = X["consent_status"].set_index(["customer_id", "consent_type"])
    cm = X["customer_master"].set_index("customer_id")
    si = X["service_interactions"]
    comp = si[si.category == "complaint"].copy()
    comp["c"] = pd.to_datetime(comp.created_at)
    comp["r"] = pd.to_datetime(comp.resolved_at).fillna(pd.Timestamp("2026-10-01"))
    by_comp = collections.defaultdict(list)
    for r in comp.itertuples():
        by_comp[r.customer_id].append((r.c, r.r))
    sent = h[h.delivery_status == "delivered"]
    unchecked = int((h.consent_checked == False).sum())  # noqa: E712 (pandas comparison)
    no_consent = during_complaint = 0
    for r in sent.itertuples():
        when = pd.Timestamp(r.decided_at)
        c = cons.loc[(r.customer_id, CHANNELS[r.channel][0])]
        # only clear cases: consent never given, or withdrawn before the action was sent
        if r.consent_checked == False and (c.status == "not_given" or (c.status == "withdrawn" and pd.Timestamp(c.updated_at) <= when)):  # noqa: E712
            no_consent += 1
        if any(a <= when <= b for a, b in by_comp.get(r.customer_id, [])):
            during_complaint += 1
    push = sent[sent.channel == "app_push"]
    push_no_app = int(sum(1 for cid in push.customer_id if not bool(cm.loc[cid, "app_installed"])))
    resp = h[h.control_group == False].response.value_counts().to_dict()  # noqa: E712
    fb = X["service_nba_feedback"]
    dismissed = fb[fb.agent_action == "dismissed"]
    return {
        "actions": int(len(h)), "delivered": int(len(sent)), "rules": int(h.rule_id.nunique()),
        "consent_not_checked": unchecked, "unchecked_and_no_consent": no_consent,
        "sales_during_open_complaint": during_complaint,
        "app_push": int(len(push)), "app_push_without_app": push_no_app,
        "responses": {k: int(v) for k, v in resp.items()},
        "agent_dismissed": int(len(dismissed)), "agent_dismissed_upset": int((dismissed.dismiss_reason == "customer_upset").sum()),
        "agent_suggestions": int(len(fb)),
    }


def violations(engine, rows):
    """Recommended sales actions that break a hard rule. Must be 0."""
    bad = 0
    for cid, row in rows.items():
        d = row["decision"]
        if d["action"] != "offer" or not d["channel"]:
            continue
        s = engine.state[cid]
        need = CHANNELS[d["channel"]][0]
        if s["consent"].get(need, {}).get("status") != "granted" or service_case(s):
            bad += 1
    return bad


def overview(engine):
    rows = engine.all()
    m = engine.marketing()
    count = collections.Counter(r["decision"]["action"] for r in rows.values())
    return {
        "summary": {k: m[k] for k in ("customers", "expected_gain_eur", "offers", "service_fixes", "held_out", "approved", "no_contact")},
        "actions": dict(count),
        "violations": violations(engine, rows),
        "legacy": legacy_audit(engine.X),
        "acceptance": engine.A.get("overall", {}),
        "cases": CASES,
    }
