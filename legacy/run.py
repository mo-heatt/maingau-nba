"""Run the full engine on the mock data and write out/nba_output.json for the app.

    python3 run.py
"""
import datetime as dt
import json
import os
from collections import Counter

from nba.engine import OUR_ASSUMPTIONS, CHANNELS, AcceptModel, decide
from nba.replay import load_events, replay
from nba.state import _d, build_state, load_assumptions, load_tables

HERE = os.path.dirname(os.path.abspath(__file__))
T = load_tables(os.path.join(HERE, "data", "maingau_nba_mockdata.xlsx"))
A = load_assumptions(T)
S = build_state(T)
CATALOG = {p["product_id"]: p for p in T["product_catalog"]}
MODEL = AcceptModel(T["nba_action_history"], OUR_ASSUMPTIONS["prior_strength"])

opens = [s.get("nl_human_opens", 0) / s["nl_delivered"] for s in S.values() if s.get("nl_delivered")]
portal = [s["portal_sessions_90d"] for s in S.values() if s.get("portal_sessions_90d")]
AVG = {"open_rate": sum(opens) / len(opens), "portal": sum(portal) / len(portal)}


def run_one(s):
    return decide(s, CATALOG, A, MODEL, AVG)


# ---------------------------------------------------------------- decide for everyone
decisions = {}
for cid, s in S.items():
    d, cands = run_one(s)
    decisions[cid] = (d, cands)

# ---------------------------------------------------------------- hard-rule audit (must be zero)
violations = []
for cid, (d, cands) in decisions.items():
    s = S[cid]
    if not d["action"]:
        continue
    if d["kind"] != "service":
        need = CHANNELS[d["channel"]][0]
        if s["consent"].get(need) != "granted":
            violations.append((cid, "channel without consent"))
        if {"open_complaint", "dunning", "cancellation"} & s["flags"]:
            violations.append((cid, "sales content during service case"))
        if d["kind"] != "retention" and s["consent"].get("profiling_analytics") != "granted":
            violations.append((cid, "personalised offer without profiling consent"))

# ---------------------------------------------------------------- legacy engine audit
consent_at = {}
for r in T["consent_status"]:
    consent_at[(r["customer_id"], r["consent_type"])] = (r["status"], _d(r["updated_at"]))
legacy = {"actions": 0, "sent": 0, "no_consent": 0, "during_case": 0, "converted": 0}
case_customers = {cid for cid, s in S.items() if {"open_complaint", "dunning", "cancellation"} & s["flags"]}
for h in T["nba_action_history"]:
    legacy["actions"] += 1
    if h["delivery_status"] != "delivered":
        continue
    legacy["sent"] += 1
    legacy["converted"] += 1 if h["converted_within_14d"] else 0
    need = CHANNELS.get(h["channel"], (None,))[0]
    st = consent_at.get((h["customer_id"], need))
    if st and st[0] != "granted" and (st[0] == "not_given" or st[1] <= _d(h["decided_at"])):
        legacy["no_consent"] += 1
    if h["customer_id"] in case_customers:
        legacy["during_case"] += 1

# ---------------------------------------------------------------- event replay
events, dups = load_events(os.path.join(HERE, "data", "event_stream_2026-10-01.jsonl"))
changes, S_after = replay(events, S, lambda s: run_one(s))
late = [e for e in events if e["delay_min"] > 60]

# ---------------------------------------------------------------- output for the app
PRODUCTS = {p["product_id"]: {"name": p["product_name"], "line": p["business_line"], "kind": p["action_type"],
                              "margin": p["annual_margin_if_bought_eur"], "churn_effect": p["churn_effect_if_bought"]}
            for p in T["product_catalog"]}
customers = []
for cid, (d, cands) in decisions.items():
    s = S[cid]
    customers.append({
        "id": cid, "since": s["since"], "city": s["city"], "household": s["household_size"],
        "clv": round(s["clv"]), "churn": round(s["churn"], 3), "margin": round(s["margin"], 2),
        "service_impact": round(s["clv_service_impact"]), "drivers": s["drivers"],
        "products": s["products"], "lines": sorted(s["lines"]),
        "consent": s["consent"], "open_tickets": s["open_tickets"], "tickets": s["tickets"],
        "history": s["history"], "contacts_30d": s.get("contacts_30d", 0),
        "failed_charges_30d": s.get("failed_charges_30d", 0),
        "signals": sorted(s["evidence"].values()),
        "decision": d,
        "candidates": [{k: c.get(k) for k in ("offer", "name", "kind", "channel", "p", "value", "signal",
                                              "blocked", "block_type")} for c in cands],
    })
customers.sort(key=lambda c: c["decision"]["value"], reverse=True)

acts = Counter(c["decision"]["action"] or "none" for c in customers)
summary = {
    "customers": len(customers),
    "actions": dict(acts),
    "expected_gain_total": round(sum(c["decision"]["value"] for c in customers), 2),
    "service_fixes": sum(1 for c in customers if c["decision"]["kind"] == "service"),
    "no_action": acts.get("none", 0),
    "control_group": sum(1 for c in customers if c["decision"]["control_group"]),
    "violations": len(violations),
    "legacy": legacy,
    "events_total": len(events) + dups, "events_duplicates": dups, "events_late": len(late),
    "events_decision": len(changes), "events_changed": sum(1 for c in changes if c["changed"]),
    "max_delay_min": max(e["delay_min"] for e in events),
}
out = {
    "generated": dt.datetime.now().isoformat(timespec="minutes"),
    "summary": summary,
    "assumptions_ours": OUR_ASSUMPTIONS,
    "assumptions_maingau": A,
    "products": PRODUCTS,
    "uplift": MODEL.uplift_table(),
    "global_rate": MODEL.g,
    "customers": customers,
    "replay": changes,
    "late_events": [{"type": e["event_type"], "customer": e["customer_id"], "delay_min": e["delay_min"],
                     "occurred_at": e["occurred_at"]} for e in sorted(late, key=lambda e: -e["delay_min"])[:12]],
}
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
with open(os.path.join(HERE, "out", "nba_output.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, separators=(",", ":"), default=list)

print(json.dumps(summary, indent=1))
print("violations:", violations[:5])
