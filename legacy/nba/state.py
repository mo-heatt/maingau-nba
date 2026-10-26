"""Step 2: build one row of signals per customer from the 15 tables.

Everything the engine decides on comes from this state, so every signal is
named, traceable to a table, and cleaned of the traps listed in the README.
"""
import datetime as dt
import re
from collections import defaultdict

import openpyxl

SNAPSHOT = dt.datetime(2026, 9, 30, 23, 59)


def _d(x):
    if x is None:
        return None
    if isinstance(x, dt.datetime):
        return x
    if isinstance(x, dt.date):
        return dt.datetime(x.year, x.month, x.day)
    return dt.datetime.fromisoformat(str(x))


def load_tables(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    out = {}
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        head = rows[0]
        out[ws.title] = [dict(zip(head, r)) for r in rows[1:]]
    return out


def load_assumptions(T):
    a = {}
    for r in T["value_assumptions"]:
        a[r["parameter"]] = float(r["value"])
    return a


def build_state(T):
    """Return {customer_id: state dict}."""
    S = {}
    for c in T["customer_master"]:
        S[c["customer_id"]] = {
            "id": c["customer_id"],
            "since": str(c["customer_since"])[:10],
            "city": c["city"],
            "household_size": c["household_size"] or 1,
            "portal_account": bool(c["portal_account"]),
            "app_installed": bool(c["app_installed"]),
            "products": [],          # human-readable holdings
            "lines": set(),          # business lines held
            "consent": {},
            "open_tickets": [],
            "tickets_12m": 0,
            "texts": [],             # customer's own words, for tone
            "flags": set(),          # signals used by the rules
            "evidence": {},          # flag -> why (for the reason line)
            "intent_boost": {},      # offer_id -> multiplier from events
        }

    def flag(cid, name, why):
        S[cid]["flags"].add(name)
        S[cid]["evidence"].setdefault(name, why)

    # value
    for v in T["customer_value"]:
        s = S[v["customer_id"]]
        s["margin"] = float(v["annual_margin_eur"])
        s["cost"] = float(v["cost_to_serve_12m_eur"])
        s["churn"] = float(v["churn_prob_12m"])
        s["clv"] = float(v["clv_eur"])
        s["clv_service_impact"] = float(v["clv_service_impact_eur"] or 0)
        s["drivers"] = [d.strip() for d in (v["churn_drivers"] or "").split(";") if d.strip()]
        for d in s["drivers"]:
            if d.startswith("price guarantee ends"):
                flag(s["id"], "guarantee_ending", "price guarantee ends within 90 days")
            elif d == "open complaint":
                flag(s["id"], "open_complaint", "open complaint")
            elif d == "low CSAT":
                flag(s["id"], "low_csat", "last satisfaction rating 1–2")
            elif d.startswith("dunning level"):
                flag(s["id"], "dunning", d)
            elif d == "cancellation pending":
                flag(s["id"], "cancellation", "cancellation received")
            elif "failed charges" in d:
                flag(s["id"], "failed_charges", d)
            elif re.match(r"\d+ tickets", d):
                flag(s["id"], "many_tickets", d)

    # consent (latest status per type)
    for r in T["consent_status"]:
        S[r["customer_id"]]["consent"][r["consent_type"]] = r["status"]

    # energy
    for e in T["energy_contracts"]:
        s = S[e["customer_id"]]
        if e["status"] == "terminated_meter_deregistration":
            flag(s["id"], "heat_pump_signal", "gas meter deregistered (likely heat pump)")
            s["products"].append(f"{e['tariff']} (gas meter deregistered)")
            continue
        s["lines"].add("energy")
        s["products"].append(e["tariff"])
        if e["commodity"] == "electricity":
            s["flags"].add("has_electricity")
        if e["commodity"] == "gas":
            s["flags"].add("has_gas")
        if e["tariff"] == "StromWärme":
            s["flags"].add("has_heatpump_tariff")
        if e["meter_type"] == "smart_meter_imsys":
            s["flags"].add("smart_meter")
        if e["feed_in_meter"]:
            flag(s["id"], "has_pv", "has PV feed-in meter")
        if (e["dunning_level"] or 0) >= 1:
            flag(s["id"], "dunning", f"dunning level {e['dunning_level']}")
            s["dunning_level"] = max(s.get("dunning_level", 0), e["dunning_level"])
        if e["status"] == "cancellation_pending" or e["cancellation_received_at"]:
            flag(s["id"], "cancellation", "cancellation received")
        if e["price_guarantee_until"]:
            g = _d(e["price_guarantee_until"])
            if SNAPSHOT - dt.timedelta(days=30) <= g <= SNAPSHOT + dt.timedelta(days=90):
                flag(s["id"], "guarantee_ending", f"price guarantee ends {g.date()}")
                s["guarantee_until"] = str(g.date())

    # mobile
    for m in T["mobile_contracts"]:
        s = S[m["customer_id"]]
        if m["status"] != "active":
            continue
        s["lines"].add("mobile")
        s["products"].append(f"{m['plan']} ({m['sim_count']} SIM)")
        s["sim_count"] = s.get("sim_count", 0) + (m["sim_count"] or 1)
        if (m["data_limit_reached_3m"] or 0) >= 2:
            flag(s["id"], "data_limit", f"hit data limit {m['data_limit_reached_3m']}× in 3 months")

    # autostrom
    for a in T["autostrom_contracts"]:
        s = S[a["customer_id"]]
        if a["status"] != "active":
            continue
        s["lines"].add("e_mobility")
        s["products"].append(f"Autostrom ({a['car_brand']} {a['car_model']})")
        s["flags"].add("has_autostrom")
        flag(s["id"], "ev_signal", f"drives an EV ({a['car_brand']} {a['car_model']})")

    # failed charging in last 30 days (late roaming CDRs are still counted by start time)
    fails = defaultdict(int)
    for c in T["charge_sessions"]:
        if c["session_status"] == "failed" and _d(c["started_at"]) >= SNAPSHOT - dt.timedelta(days=30):
            fails[c["customer_id"]] += 1
    for cid, n in fails.items():
        S[cid]["failed_charges_30d"] = n
        if n >= 3:
            flag(cid, "failed_charges", f"{n} failed charging sessions in 30 days")

    # shop (guest orders have no customer_id: skipped; returned/cancelled lines don't count)
    for o in T["shop_orders"]:
        cid = o["customer_id"]
        if not cid or o["order_status"] in ("returned", "cancelled"):
            continue
        s = S[cid]
        name = o["product_name"] or ""
        s.setdefault("bought", set()).add(name)
        if "Wallbox" in name:
            flag(cid, "has_wallbox", f"bought a wallbox ({str(o['order_created_at'])[:7]})")
            flag(cid, "ev_signal", "bought a wallbox")
        if "Ladekabel" in name:
            flag(cid, "ev_signal", "bought a Type 2 charging cable")
        if "Balkonkraftwerk" in name:
            flag(cid, "has_pv", "bought a plug-in solar kit")
        if "Thermostat" in name:
            s["flags"].add("has_thermostats")
        if "Smart Plug" in name:
            s["flags"].add("has_smart_plugs")

    # HEMS
    for h in T["hems_devices"]:
        s = S[h["customer_id"]]
        t = h["device_type"]
        if t == "hems_gateway":
            s["lines"].add("smart_living")
            s["flags"].add("has_hems")
            s["products"].append("HEMS")
            if h["connection_status"] == "offline":
                flag(s["id"], "hems_offline", "HEMS gateway offline")
        elif t == "pv_inverter":
            flag(s["id"], "has_pv", "has a PV inverter")
        elif t == "home_battery":
            s["flags"].add("has_battery")
        elif t == "wallbox":
            flag(s["id"], "has_wallbox", "has a wallbox")
            flag(s["id"], "ev_signal", "has a wallbox")
        elif t == "heat_pump":
            flag(s["id"], "heat_pump_signal", "heat pump connected to HEMS")
    for r in T["hems_telemetry_daily"]:
        if (r["heat_pump_kwh"] or 0) > 0:
            flag(r["customer_id"], "heat_pump_signal", "heat pump consumption in HEMS data")
        if (r["ev_charging_kwh"] or 0) > 0:
            flag(r["customer_id"], "ev_signal", "EV charging at home in HEMS data")

    # service
    for t in T["service_interactions"]:
        s = S[t["customer_id"]]
        created = _d(t["created_at"])
        if created >= SNAPSHOT - dt.timedelta(days=365):
            s["tickets_12m"] += 1
        if t["message_text"]:
            s["texts"].append(t["message_text"])
        if t["status"] == "open":
            s["open_tickets"].append({
                "id": t["ticket_id"], "category": t["category"], "channel": t["channel"],
                "created": str(created)[:16],
                "text": t["message_text"] or t["call_note"] or "",
                "repeat": bool(t["repeat_of_ticket_id"]),
            })
            if t["category"] == "complaint":
                flag(s["id"], "open_complaint", "open complaint")
            else:
                flag(s["id"], "open_ticket", f"open {t['category']} ticket")
        s.setdefault("tickets", []).append({
            "created": str(created)[:10], "category": t["category"], "status": t["status"],
            "channel": t["channel"], "csat": t["csat_1to5"],
            "text": (t["message_text"] or t["call_note"] or "")[:220],
        })
    for c in T["call_transcripts"]:
        lines = [l[len("Kunde:"):].strip() for l in (c["transcript"] or "").split("\n") if l.startswith("Kunde:")]
        S[c["customer_id"]]["texts"].extend(lines)

    # engagement (Apple MPP machine opens are not human opens)
    nl = defaultdict(lambda: [0, 0, 0])  # delivered, human opens, clicks
    for r in T["newsletter_performance"]:
        if not r["delivered"]:
            continue
        x = nl[r["customer_id"]]
        x[0] += 1
        if r["opened_at"] and r["open_client_class"] == "human":
            x[1] += 1
        if r["clicked_at"]:
            x[2] += 1
    for cid, (d_, o, c) in nl.items():
        S[cid]["nl_delivered"], S[cid]["nl_human_opens"], S[cid]["nl_clicks"] = d_, o, c
    ps = defaultdict(int)
    for r in T["portal_sessions"]:
        if _d(r["session_start"]) >= SNAPSHOT - dt.timedelta(days=90):
            ps[r["customer_id"]] += 1
    for cid, n in ps.items():
        S[cid]["portal_sessions_90d"] = n

    # past marketing contacts (for fatigue) and history for the 360 view
    for a in T["nba_action_history"]:
        s = S[a["customer_id"]]
        decided = _d(a["decided_at"])
        if a["delivery_status"] == "delivered" and decided >= SNAPSHOT - dt.timedelta(days=30):
            s["contacts_30d"] = s.get("contacts_30d", 0) + 1
        s.setdefault("history", []).append({
            "date": str(decided)[:10], "offer": a["offer_id"], "channel": a["channel"],
            "tone": a["tonality"], "response": a["response"], "converted": bool(a["converted_within_14d"]),
        })

    for s in S.values():
        s["history"] = sorted(s.get("history", []), key=lambda h: h["date"], reverse=True)[:6]
        s["tickets"] = sorted(s.get("tickets", []), key=lambda h: h["created"], reverse=True)[:5]
        s.setdefault("sim_count", 0)
    return S
