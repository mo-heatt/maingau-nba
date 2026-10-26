from .constants import CONTRACT, BEHAVIOURAL
from .content import customer_lines, tone_from_texts

CART_MAP = {"Smart Plug": "P-SH-04", "Balkonkraftwerk": "P-SH-01", "Wallbox": "P-SH-02", "Thermostat": "P-SH-03"}
CLICK_MAP = {"smart_living": "clicked_smart_living", "energy": "clicked_energy", "mobile": "clicked_mobile", "shop": "clicked_shop",
             "e_mobility": "clicked_e_mobility", "heat_pump": "clicked_heat_pump"}

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
            s["signals"]["open_complaint"] = {"value": "new", "class": CONTRACT}
            s["evidence"]["open_complaint"].append(f"New complaint {e['occurred_at'][:16]} via {pl.get('channel')}")
            return f"New complaint via {pl.get('channel')}"
        return f"New {pl.get('category')} ticket via {pl.get('channel')}"
    if t == "ticket_updated":
        return f"Ticket update: {pl.get('note', pl.get('status'))}"
    if t == "dunning_level_changed":
        old = s["signals"].get("dunning_level", {"value": 0})["value"]
        s["signals"]["dunning_level"] = {"value": pl["new_level"], "class": CONTRACT}
        s["evidence"]["dunning_level"].append(f"Dunning level {pl['old_level']} → {pl['new_level']}")
        if pl["new_level"] >= 2 and old < 2:
            s["live_churn_add"] = {**s.get("live_churn_add", {}), "dunning": P["dunning_ge2"]}
        return f"Dunning level {pl['old_level']} → {pl['new_level']}"
    if t == "contract_cancellation_received":
        s["signals"]["cancellation_pending"] = {"value": True, "class": CONTRACT}
        s["evidence"]["cancellation_pending"].append(f"Cancellation received {e['occurred_at'][:10]} ({pl.get('commodity')})")
        return f"Cancellation received ({pl.get('commodity')})"
    if t == "charge_session_failed":
        s["failed_charges_30d"] = s.get("failed_charges_30d", 0) + 1
        if s["failed_charges_30d"] >= 3 and "failed_charges" not in s["signals"]:
            s["signals"]["failed_charges"] = {"value": s["failed_charges_30d"], "class": CONTRACT}
            s["evidence"]["failed_charges"].append(f"{s['failed_charges_30d']} failed charging sessions in 30 days")
            s["live_churn_add"] = {**s.get("live_churn_add", {}), "failed": P["failed_charges_30d_ge3"]}
        return f"Charging failed ({pl.get('charge_type')}) – {s['failed_charges_30d']} in 30 days"
    if t == "gas_meter_deregistration_received":
        s["signals"]["gas_meter_deregistered"] = {"value": pl.get("effective_date"), "class": CONTRACT}
        s["evidence"]["gas_meter_deregistered"].append(f"Gas meter deregistration received, effective {pl.get('effective_date')} – likely heat pump")
        return "Gas meter deregistration received"
    if t == "cart_abandoned":
        name = pl.get("product_name", "")
        for k, o in CART_MAP.items():
            if k in name:
                s.setdefault("cart_intent", {})[o] = f"abandoned cart: {name}"
                s["signals"].setdefault("shop_customer", {"value": True, "class": CONTRACT})
        return f"Abandoned cart: {name}"
    if t == "order_placed":
        s["holds"].add("order_" + pl.get("product_name", ""))
        return f"Order placed: {pl.get('product_name')}"
    if t == "newsletter_clicked":
        tgt = pl.get("click_target", "")
        for k, sig in CLICK_MAP.items():
            if tgt.startswith(k):
                s["signals"][sig] = {"value": 1, "class": BEHAVIOURAL}
                s["evidence"][sig].append(f"Clicked newsletter link: {tgt}")
        return f"Newsletter click: {tgt}"
    if t == "call_transcript_ready":
        s["texts"].extend(customer_lines(pl.get("transcript", "")))
        tone, why, *_ = tone_from_texts(s["texts"])
        s["tone"], s["tone_reason"] = tone, why
        return "Call transcript arrived – tone re-checked"
    if t == "agent_nba_feedback":
        return f"Agent {pl.get('agent_action')} suggestion {pl.get('suggested_offer_id')} ({pl.get('dismiss_reason')})"
    if t == "hems_device_offline":
        s["signals"]["hems_offline"] = {"value": True, "class": CONTRACT}
        return "HEMS gateway went offline"
    return None
