"""Event replay, learning metrics, self-checks, and JSON export for the web app."""
import json, copy, collections, datetime as dt
from pathlib import Path
import pandas as pd
import engine as E

OUT = Path(__file__).parent / "out"

CART_MAP = {"Smart Plug": "P-SH-04", "Balkonkraftwerk": "P-SH-01", "Wallbox": "P-SH-02", "Thermostat": "P-SH-03"}
CLICK_MAP = {"smart_living": "clicked_smart_living", "energy": "clicked_energy", "mobile": "clicked_mobile", "shop": "clicked_shop",
             "e_mobility": "clicked_e_mobility", "heat_pump": "clicked_heat_pump"}


def decide(s, ctx):
    X, P, A, catalog, fcr = ctx
    sc = E.score_customer(s, X, P, A, catalog, fcr)
    d = E.arbitrate(s, sc)
    return sc, d, E.message(s, d)


def label(d):
    p = d.get("pick")
    if d["action"] == "offer":
        return f"{p['name']} · {p['channel_label']}"
    return d["title"]


def apply_event(s, e, P):
    """Mutate state with one event. Returns a short note, or None if the event doesn't touch decision inputs."""
    t, pl = e["event_type"], e.get("payload") or {}
    if t == "consent_changed":
        s["consent"].setdefault(pl["consent_type"], {})["status"] = pl["new_status"]
        return f"Consent {pl['consent_type']} → {pl['new_status']} ({pl.get('source', '')})"
    if t == "ticket_created":
        s["open_tickets"].append({"category": pl.get("category"), "created_at": e["occurred_at"], "channel": pl.get("channel")})
        if pl.get("category") == "complaint":
            if "open_complaint" not in s["signals"]:
                s["live_churn_add"] = {**s.get("live_churn_add", {}), "open_complaint": P["open_complaint"]}
            s["signals"]["open_complaint"] = {"value": "new", "class": E.CONTRACT}
            s["evidence"]["open_complaint"].append(f"New complaint {e['occurred_at'][:16]} via {pl.get('channel')}")
            return f"New complaint via {pl.get('channel')}"
        return f"New {pl.get('category')} ticket via {pl.get('channel')}"
    if t == "ticket_updated":
        return f"Ticket update: {pl.get('note', pl.get('status'))}"
    if t == "dunning_level_changed":
        old = s["signals"].get("dunning_level", {"value": 0})["value"]
        s["signals"]["dunning_level"] = {"value": pl["new_level"], "class": E.CONTRACT}
        s["evidence"]["dunning_level"].append(f"Dunning level {pl['old_level']} → {pl['new_level']}")
        if pl["new_level"] >= 2 and old < 2:
            s["live_churn_add"] = {**s.get("live_churn_add", {}), "dunning": P["dunning_ge2"]}
        return f"Dunning level {pl['old_level']} → {pl['new_level']}"
    if t == "contract_cancellation_received":
        s["signals"]["cancellation_pending"] = {"value": True, "class": E.CONTRACT}
        s["evidence"]["cancellation_pending"].append(f"Cancellation received {e['occurred_at'][:10]} ({pl.get('commodity')})")
        return f"Cancellation received ({pl.get('commodity')})"
    if t == "charge_session_failed":
        s["failed_charges_30d"] = s.get("failed_charges_30d", 0) + 1
        if s["failed_charges_30d"] >= 3 and "failed_charges" not in s["signals"]:
            s["signals"]["failed_charges"] = {"value": s["failed_charges_30d"], "class": E.CONTRACT}
            s["evidence"]["failed_charges"].append(f"{s['failed_charges_30d']} failed charging sessions in 30 days")
            s["live_churn_add"] = {**s.get("live_churn_add", {}), "failed": P["failed_charges_30d_ge3"]}
        return f"Charging failed ({pl.get('charge_type')}) – {s['failed_charges_30d']} in 30 days"
    if t == "gas_meter_deregistration_received":
        s["signals"]["gas_meter_deregistered"] = {"value": pl.get("effective_date"), "class": E.CONTRACT}
        s["evidence"]["gas_meter_deregistered"].append(f"Gas meter deregistration received, effective {pl.get('effective_date')} – likely heat pump")
        return "Gas meter deregistration received"
    if t == "cart_abandoned":
        name = pl.get("product_name", "")
        for k, o in CART_MAP.items():
            if k in name:
                s.setdefault("cart_intent", {})[o] = f"abandoned cart: {name}"
                s["signals"].setdefault("shop_customer", {"value": True, "class": E.CONTRACT})
        return f"Abandoned cart: {name}"
    if t == "order_placed":
        s["holds"].add("order_" + pl.get("product_name", ""))
        return f"Order placed: {pl.get('product_name')}"
    if t == "newsletter_clicked":
        tgt = pl.get("click_target", "")
        for k, sig in CLICK_MAP.items():
            if tgt.startswith(k):
                s["signals"][sig] = {"value": 1, "class": E.BEHAVIOURAL}
                s["evidence"][sig].append(f"Clicked newsletter link: {tgt}")
        return f"Newsletter click: {tgt}"
    if t == "call_transcript_ready":
        s["texts"].extend(E.customer_lines(pl.get("transcript", "")))
        tone, why, *_ = E.tone_from_texts(s["texts"])
        s["tone"], s["tone_reason"] = tone, why
        return "Call transcript arrived – tone re-checked"
    if t == "agent_nba_feedback":
        return f"Agent {pl.get('agent_action')} suggestion {pl.get('suggested_offer_id')} ({pl.get('dismiss_reason')})"
    if t == "hems_device_offline":
        s["signals"]["hems_offline"] = {"value": True, "class": E.CONTRACT}
        return "HEMS gateway went offline"
    return None


def replay(state, events, ctx, base):
    P = ctx[1]
    seen = set(); dups = 0; rows = []
    evs = sorted(events, key=lambda e: e["occurred_at"])
    live = {}
    for e in evs:
        if e["event_id"] in seen:
            dups += 1; continue
        seen.add(e["event_id"])
        cid = e["customer_id"]
        if cid not in state:
            continue
        s = live.get(cid) or copy.deepcopy(state[cid])
        before = live.get(cid + "_dec") or base[cid][1]
        note = apply_event(s, e, P)
        if note is None:
            continue
        live[cid] = s
        sc, d, msg = decide(s, ctx)
        live[cid + "_dec"] = d
        occ = dt.datetime.fromisoformat(e["occurred_at"]); ing = dt.datetime.fromisoformat(e["ingested_at"])
        rows.append({"event_id": e["event_id"], "occurred_at": e["occurred_at"], "ingested_at": e["ingested_at"],
                     "lag_min": round((ing - occ).total_seconds() / 60), "customer_id": cid, "type": e["event_type"],
                     "source": e["source_system"], "note": note, "before": label(before), "after": label(d),
                     "changed": label(before) != label(d), "after_reason": d["reason"],
                     "after_dclv": d["pick"]["dclv"] if d.get("pick") else None})
    lag = [r["lag_min"] for r in rows]
    return rows, dups


CONSENT_FOR = {"newsletter_email": "newsletter_email", "portal_popup": "portal_app_personalisation", "app_push": "portal_app_personalisation",
               "sms": "marketing_sms", "outbound_call": "marketing_phone", "email": "marketing_email"}


def legacy_audit(X):
    h = X["nba_action_history"]; cons = X["consent_status"].set_index(["customer_id", "consent_type"])
    si = X["service_interactions"]; comp = si[si.category == "complaint"].copy()
    comp["c"] = pd.to_datetime(comp.created_at); comp["r"] = pd.to_datetime(comp.resolved_at).fillna(pd.Timestamp("2026-10-01"))
    en = X["energy_contracts"]; dun = set(en[en.dunning_level >= 1].customer_id)
    sent = h[h.delivery_status == "delivered"]
    v_consent = 0; v_complaint = 0; v_dunning = 0; unchecked = int((h.consent_checked == False).sum())
    by_comp = collections.defaultdict(list)
    for r in comp.itertuples():
        by_comp[r.customer_id].append((r.c, r.r))
    for r in sent.itertuples():
        when = pd.Timestamp(r.decided_at)
        ct = CONSENT_FOR[r.channel]
        c = cons.loc[(r.customer_id, ct)]
        upd = pd.Timestamp(c.updated_at)
        # count only clear cases: consent never given, or withdrawn before the action was sent
        if r.consent_checked == False and (c.status == "not_given" or (c.status == "withdrawn" and upd <= when)):
            v_consent += 1
        if any(a <= when <= b for a, b in by_comp.get(r.customer_id, [])):
            v_complaint += 1
        if r.customer_id in dun and not str(r.offer_id).startswith("P-SV"):
            v_dunning += 1
    total = len(h)
    resp = h[h.control_group == False].response.value_counts().to_dict()
    return {"actions": int(total), "delivered": int(len(sent)), "consent_not_checked": unchecked, "unchecked_and_no_consent": v_consent,
            "sales_during_open_complaint": v_complaint, "responses": {k: int(v) for k, v in resp.items()}}


def self_check(cust):
    """Every recommended marketing action must have channel consent and no exclusion. Returns violations (should be 0)."""
    bad = []
    for c in cust:
        d = c["decision"]
        p = d.get("pick")
        if d["action"] != "offer" or not p or p["offer"] == "P-SV-01":
            continue
        need = E.CHANNELS[p["channel"]][0]
        if c["consent"].get(need) != "granted":
            bad.append((c["customer_id"], "consent", p["channel"]))
        if c["service_case"]:
            bad.append((c["customer_id"], "exclusion", c["service_case"]))
    return bad


def export(X, events, P, A, catalog, fcr, state, out):
    ctx = (X, P, A, catalog, fcr)
    cust = []
    for cid, s in state.items():
        sc, d, msg = out[cid]
        cust.append({
            "customer_id": cid, "city": s["city"], "customer_since": s["customer_since"], "birth_year": s["birth_year"], "household_size": s["household_size"],
            "portal_account": s["portal_account"], "app_installed": s["app_installed"], "language": s["language"],
            "consent": {k: v["status"] for k, v in s["consent"].items()},
            "value": s["value"], "clv_now": sc["clv_now"], "churn_now": sc["churn_now"], "churn_parts": sc["churn_parts"],
            "products": s["products"], "signals": {k: {"value": v["value"], "class": v["class"], "evidence": s["evidence"].get(k, [])} for k, v in s["signals"].items()},
            "open_tickets": s["open_tickets"], "recent_tickets": s["recent_tickets"], "tone": s["tone"], "tone_reason": s["tone_reason"], "tone_sample": s["tone_sample"],
            "contacts_30d": s["contacts_30d"], "portal_sessions_90d": s["portal_sessions_90d"], "email_engagement": s["email_engagement"],
            "legacy_actions": s["legacy_actions"], "service_case": sc["service_case"], "profiling": sc["profiling"],
            "channels": sc["channels"], "candidates": sc["candidates"], "decision": d, "message": msg,
            "cancellation_pending": "cancellation_pending" in s["signals"],
        })
    rows, dups = replay(state, events, ctx, out)
    viol = self_check(cust)
    mix = collections.Counter((c["decision"]["pick"]["offer"] if c["decision"]["action"] == "offer" else c["decision"]["action"]) for c in cust)
    data = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "snapshot": "2026-09-30 23:59", "settings": E.SETTINGS, "signal_lift": E.SIGNAL_LIFT, "intent_lift": E.INTENT_LIFT,
        "params": P, "fcr_rate": round(fcr, 3),
        "acceptance": {"global": round(A["global"], 4), "channel_factor": {k: round(v, 3) for k, v in A["channel_factor"].items()},
                       "offer_rate": {k: round(v, 4) for k, v in A["offer_rate"].items()}, "uplift": A["uplift"], "overall": A["overall"]},
        "catalog": [{"id": r.Index, "name": r.product_name, "line": r.business_line, "type": r.action_type, "margin": None if pd.isna(r.annual_margin_if_bought_eur) else float(r.annual_margin_if_bought_eur)}
                    for r in catalog.itertuples()],
        "customers": cust, "replay": rows, "replay_duplicates": dups,
        "legacy": legacy_audit(X), "self_check_violations": len(viol), "mix": dict(mix),
    }
    OUT.mkdir(exist_ok=True)
    with open(OUT / "engine_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    print("customers", len(cust), "| mix", dict(mix))
    print("self-check violations:", len(viol), viol[:5])
    print("replay rows", len(rows), "changed", sum(r["changed"] for r in rows), "dups", dups)
    print("legacy", data["legacy"])
    return data


if __name__ == "__main__":
    export(*E.run())
