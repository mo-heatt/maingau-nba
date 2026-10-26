"""Event replay: feed the 1 October event stream into the customer state, in the
order the system receives it (ingested_at), and re-decide the affected customer.
"""
import copy
import datetime as dt
import json

CART_TO_OFFER = {"Smart Plug 4er-Set": "P-SH-04", "Balkonkraftwerk 800 W": "P-SH-01", "Wallbox 11 kW": "P-SH-02",
                 "Smarte Thermostate 3er": "P-SH-03"}
CLICK_TO_OFFERS = {"smart_living_landingpage": ["P-SL-01", "P-SL-02", "P-SL-03"],
                   "energy_landingpage": ["P-EN-02", "P-EN-03", "P-EN-05"],
                   "mobile_landingpage": ["P-MO-01", "P-MO-02", "P-MO-03"],
                   "shop_landingpage": ["P-SH-01", "P-SH-02", "P-SH-03", "P-SH-04"],
                   "autostrom_landingpage": ["P-AS-01"]}

# events that can change a decision; the rest only update engagement
DECISION_EVENTS = {"consent_changed", "ticket_created", "ticket_updated", "contract_cancellation_received",
                   "dunning_level_changed", "charge_session_failed", "gas_meter_deregistration_received",
                   "cart_abandoned", "order_placed", "newsletter_clicked", "call_transcript_ready",
                   "agent_nba_feedback", "hems_device_offline", "mobile_data_threshold"}


def load_events(path):
    ev = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    seen, out, dups = set(), [], 0
    for e in ev:
        if e["event_id"] in seen:
            dups += 1
            continue
        seen.add(e["event_id"])
        occ = dt.datetime.fromisoformat(e["occurred_at"])
        ing = dt.datetime.fromisoformat(e["ingested_at"])
        e["delay_min"] = round((ing - occ).total_seconds() / 60, 1)
        out.append(e)
    out.sort(key=lambda e: e["ingested_at"])
    return out, dups


def apply(e, s):
    """Mutate state s with event e. Return a short German-free description of what changed, or None."""
    t, p = e["event_type"], e.get("payload") or {}
    f, ev = s["flags"], s["evidence"]

    def flag(k, why):
        f.add(k)
        ev[k] = why

    if t == "consent_changed":
        s["consent"][p["consent_type"]] = p["new_status"]
        return f"{p['consent_type'].replace('_', ' ')} consent {p['new_status']}"
    if t == "ticket_created":
        cat = p.get("category")
        s["open_tickets"].append({"id": "new", "category": cat, "channel": p.get("channel"),
                                  "created": e["occurred_at"][:16], "text": "", "repeat": False})
        if cat == "complaint":
            flag("open_complaint", "new complaint ticket today")
            return "new complaint"
        flag("open_ticket", f"new {cat} ticket today")
        return f"new {cat} ticket"
    if t == "ticket_updated":
        flag("open_complaint", "complaint still open: customer asks for a callback")
        return "complaint escalated: customer asks for a callback"
    if t == "contract_cancellation_received":
        flag("cancellation", "cancellation received today")
        s["churn"] = 0.95
        return "cancellation received"
    if t == "dunning_level_changed":
        s["dunning_level"] = p["new_level"]
        flag("dunning", f"dunning level {p['new_level']}")
        return f"dunning level {p['old_level']} → {p['new_level']}"
    if t == "charge_session_failed":
        s["failed_charges_30d"] = s.get("failed_charges_30d", 0) + 1
        if s["failed_charges_30d"] >= 3:
            flag("failed_charges", f"{s['failed_charges_30d']} failed charging sessions in 30 days")
        return f"charging failed ({s['failed_charges_30d']} in 30 days)"
    if t == "gas_meter_deregistration_received":
        flag("heat_pump_signal", "gas meter deregistered today (likely heat pump)")
        return "gas meter deregistered"
    if t == "cart_abandoned":
        o = CART_TO_OFFER.get(p.get("product_name"))
        if o:
            s["intent_boost"][o] = 1.5
        return f"left {p.get('product_name')} in the cart"
    if t == "order_placed":
        name = p.get("product_name", "")
        s.setdefault("bought", set()).add(name)
        if "Wallbox" in name:
            flag("has_wallbox", "bought a wallbox today")
            flag("ev_signal", "bought a wallbox today")
        return f"ordered {name}"
    if t == "newsletter_clicked":
        for o in CLICK_TO_OFFERS.get(p.get("click_target"), []):
            s["intent_boost"][o] = 1.3
        return f"clicked {p.get('click_target', '').replace('_', ' ')}"
    if t == "call_transcript_ready":
        tr = p.get("transcript", "")
        s["texts"].extend(l[len("Kunde:"):].strip() for l in tr.split("\n") if l.startswith("Kunde:"))
        if "Preisgarantie" in tr:
            flag("guarantee_ending", "said on the phone: comparing offers, price guarantee ends")
            s["intent_boost"]["P-EN-02"] = 1.5
            return "call: comparing prices, guarantee ending"
        return "call transcript received"
    if t == "agent_nba_feedback":
        if p.get("dismiss_reason") == "customer_upset":
            flag("upset", "agent reports customer is upset")
            return "agent: customer upset"
        return "agent feedback"
    if t == "hems_device_offline":
        flag("hems_offline", "HEMS gateway went offline")
        return "HEMS gateway offline"
    if t == "mobile_data_threshold":
        if (p.get("threshold_pct") or 0) >= 80:
            s["intent_boost"]["P-MO-02"] = 1.2
        return f"used {p.get('threshold_pct')}% of mobile data"
    return None


def replay(events, S, decide_fn):
    S2 = copy.deepcopy(S)
    changes = []
    for e in events:
        cid = e.get("customer_id")
        if e["event_type"] not in DECISION_EVENTS or cid not in S2:
            if e["event_type"] == "portal_login" and cid in S2:
                S2[cid]["portal_sessions_90d"] = S2[cid].get("portal_sessions_90d", 0) + 1
            continue
        before, _ = decide_fn(S2[cid])
        what = apply(e, S2[cid])
        after, cands = decide_fn(S2[cid])
        changed = (before["action"], before["channel"]) != (after["action"], after["channel"])
        changes.append({
            "event_id": e["event_id"], "customer": cid, "type": e["event_type"], "what": what,
            "occurred_at": e["occurred_at"], "ingested_at": e["ingested_at"], "delay_min": e["delay_min"],
            "before": {"action": before["action"], "name": before["name"], "channel": before["channel"], "value": before["value"]},
            "after": {"action": after["action"], "name": after["name"], "channel": after["channel"], "value": after["value"],
                      "reason": after["reason"]},
            "changed": changed,
        })
    return changes, S2
