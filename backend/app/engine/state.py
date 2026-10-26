import collections
import datetime as dt
import pandas as pd
from .constants import SNAPSHOT, DECISION_DAY, CONTRACT, BEHAVIOURAL
from .utils import ts
from .content import tone_from_texts, customer_lines


def build_state(X):
    cm = X["customer_master"].set_index("customer_id")
    cv = X["customer_value"].set_index("customer_id")
    en = X["energy_contracts"]; mo = X["mobile_contracts"]; au = X["autostrom_contracts"]
    so = X["shop_orders"]; hd = X["hems_devices"]; tel = X["hems_telemetry_daily"]
    si = X["service_interactions"]; ct = X["call_transcripts"]; cs = X["charge_sessions"]
    nlp = X["newsletter_performance"].merge(X["newsletter_campaigns"][["campaign_id", "product_focus", "tonality", "sent_at"]], on="campaign_id")
    ps = X["portal_sessions"]; hist = X["nba_action_history"]; cons = X["consent_status"]

    consent = collections.defaultdict(dict)
    for r in cons.itertuples():
        consent[r.customer_id][r.consent_type] = {"status": r.status, "updated_at": str(r.updated_at), "source": r.source, "doi": None if pd.isna(r.double_opt_in_confirmed_at) else str(r.double_opt_in_confirmed_at)}

    state = {}
    for cid, c in cm.iterrows():
        v = cv.loc[cid]
        s = {"customer_id": cid, "city": c.city, "customer_since": str(c.customer_since)[:10], "birth_year": int(c.birth_year) if not pd.isna(c.birth_year) else None,
             "household_size": int(c.household_size) if not pd.isna(c.household_size) else 1,
             "portal_account": bool(c.portal_account), "app_installed": bool(c.app_installed), "language": c.preferred_contact_language,
             "consent": consent[cid],
             "value": {"annual_margin": float(v.annual_margin_eur), "cost_to_serve": float(v.cost_to_serve_12m_eur), "service_cost": float(v.service_cost_12m_eur),
                       "churn": float(v.churn_prob_12m), "clv": float(v.clv_eur), "clv_service_impact": float(v.clv_service_impact_eur),
                       "churn_drivers": [] if pd.isna(v.churn_drivers) else [d.strip() for d in str(v.churn_drivers).split(";")],
                       "lines": int(v.active_business_lines)}}
        state[cid] = s

    for cid, s in state.items():
        s["products"] = []; s["holds"] = set(); s["signals"] = {}; s["evidence"] = collections.defaultdict(list)
        s["open_tickets"] = []; s["recent_tickets"] = []; s["texts"] = []

    def sig(cid, key, val, cls, why):
        st = state[cid]
        st["signals"][key] = {"value": val, "class": cls}
        st["evidence"][key].append(why)

    # energy
    for r in en.itertuples():
        st = state[r.customer_id]
        active = r.status in ("active", "cancellation_pending")
        st["products"].append({"line": "energy", "name": r.tariff, "commodity": r.commodity, "status": r.status,
                               "price_guarantee_until": None if pd.isna(r.price_guarantee_until) else str(r.price_guarantee_until)[:10],
                               "meter_type": r.meter_type, "dunning_level": int(r.dunning_level)})
        if active:
            st["holds"].add("electricity" if r.commodity == "electricity" else "gas")
            st["holds"].add(r.tariff)
            if r.meter_type == "smart_meter_imsys":
                sig(r.customer_id, "smart_meter", True, CONTRACT, f"{r.tariff}: smart meter (iMSys)")
            g = ts(r.price_guarantee_until)
            if g and DECISION_DAY - dt.timedelta(days=30) <= g <= DECISION_DAY + dt.timedelta(days=90):
                sig(r.customer_id, "guarantee_ending", g.strftime("%Y-%m-%d"), CONTRACT, f"{r.tariff} price guarantee until {g:%d.%m.%Y}")
        if r.status == "cancellation_pending":
            sig(r.customer_id, "cancellation_pending", True, CONTRACT, f"{r.tariff}: cancellation received {str(r.cancellation_received_at)[:10]}")
        if r.status == "terminated_meter_deregistration":
            sig(r.customer_id, "gas_meter_deregistered", str(r.meter_deregistered_at)[:10], CONTRACT, f"Gas meter deregistered {str(r.meter_deregistered_at)[:10]} – likely switched to heat pump")
        if int(r.dunning_level) > 0:
            prev = state[r.customer_id]["signals"].get("dunning_level", {"value": 0})["value"]
            sig(r.customer_id, "dunning_level", max(prev, int(r.dunning_level)), CONTRACT, f"{r.tariff}: dunning level {int(r.dunning_level)}")

    for r in mo.itertuples():
        st = state[r.customer_id]
        st["products"].append({"line": "mobile", "name": r.plan, "status": r.status, "sim_count": int(r.sim_count), "data_limit_reached_3m": int(r.data_limit_reached_3m)})
        if r.status == "active":
            st["holds"].add("mobile")
            if int(r.data_limit_reached_3m) >= 2:
                sig(r.customer_id, "data_limit_reached", int(r.data_limit_reached_3m), BEHAVIOURAL, f"Data limit reached {int(r.data_limit_reached_3m)}× in 3 months")
            if st["household_size"] > int(r.sim_count):
                sig(r.customer_id, "household_more_than_sims", True, CONTRACT, f"Household of {st['household_size']}, {int(r.sim_count)} SIM(s)")

    for r in au.itertuples():
        st = state[r.customer_id]
        st["products"].append({"line": "autostrom", "name": r.product, "status": r.status, "car": f"{r.car_brand} {r.car_model}"})
        if r.status == "active":
            st["holds"].add("autostrom"); sig(r.customer_id, "ev_driver", True, CONTRACT, f"Autostrom customer, drives {r.car_brand} {r.car_model}")

    for r in hd.itertuples():
        st = state[r.customer_id]
        st["products"].append({"line": "smart_living", "name": r.device_type, "status": r.connection_status})
        st["holds"].add("dev_" + r.device_type)
        if r.device_type == "hems_gateway" and r.connection_status == "offline":
            sig(r.customer_id, "hems_offline", True, CONTRACT, "HEMS gateway offline")

    tel_hp = tel.groupby("customer_id").heat_pump_kwh.sum(min_count=1)
    tel_ev = tel.groupby("customer_id").ev_charging_kwh.sum(min_count=1)
    for cid, val in tel_hp.items():
        if val and val > 0:
            sig(cid, "heat_pump_usage", round(float(val)), BEHAVIOURAL, f"Smart-home data: {val:.0f} kWh heat pump use in September")
    for cid, val in tel_ev.items():
        if val and val > 0:
            sig(cid, "ev_home_charging", round(float(val)), BEHAVIOURAL, f"Smart-home data: {val:.0f} kWh EV charging at home in September")

    for r in so[so.customer_id.notna()].itertuples():
        st = state[r.customer_id]
        st["holds"].add("order_" + str(r.product_name))
        if r.order_status not in ("cancelled", "returned"):
            if "Wallbox" in str(r.product_name):
                sig(r.customer_id, "wallbox_bought", str(r.order_created_at)[:10], CONTRACT, f"Bought {r.product_name} in shop on {str(r.order_created_at)[:10]}")
        st["signals"].setdefault("shop_customer", {"value": True, "class": CONTRACT})

    # service
    si = si.sort_values("created_at")
    for r in si.itertuples():
        st = state[r.customer_id]
        txt = r.message_text if isinstance(r.message_text, str) else None
        if txt:
            st["texts"].append(txt)
        t = {"ticket_id": r.ticket_id, "created_at": str(r.created_at)[:16], "channel": r.channel, "category": r.category, "status": r.status,
             "text": txt or (r.call_note if isinstance(r.call_note, str) else ""), "csat": None if pd.isna(r.csat_1to5) else int(r.csat_1to5),
             "resolution": None if pd.isna(r.resolution_code) else r.resolution_code, "repeat": isinstance(r.repeat_of_ticket_id, str)}
        st["recent_tickets"].append(t)
        if r.status == "open":
            st["open_tickets"].append(t)
            if r.category == "complaint":
                sig(r.customer_id, "open_complaint", r.ticket_id, CONTRACT, f"Open complaint since {str(r.created_at)[:10]}")
    for r in ct.itertuples():
        state[r.customer_id]["texts"].extend(customer_lines(r.transcript))

    # failed charging, last 30 days of the snapshot
    cs = cs.copy(); cs["started"] = pd.to_datetime(cs.started_at)
    recent_fail = cs[(cs.session_status == "failed") & (cs.started >= SNAPSHOT - dt.timedelta(days=30))].groupby("customer_id").size()
    for cid, n in recent_fail.items():
        state[cid]["failed_charges_30d"] = int(n)
        if n >= 3:
            sig(cid, "failed_charges", int(n), CONTRACT, f"{n} failed charging sessions in the last 30 days")

    # newsletter engagement, human opens only (Apple MPP prefetch = machine open)
    nlp = nlp[nlp.delivered == True]
    for cid, g in nlp.groupby("customer_id"):
        human_open = g.opened_at.notna() & (g.open_client_class == "human")
        st = state[cid]
        st["email_engagement"] = {"delivered": int(len(g)), "human_opens": int(human_open.sum()),
                                  "machine_opens": int((g.open_client_class == "apple_mpp_prefetch").sum()), "clicks": int(g.clicked_at.notna().sum())}
        clicks = g[g.clicked_at.notna()]
        for focus, n in clicks.product_focus.value_counts().items():
            if n >= 1:
                sig(cid, "clicked_" + str(focus), int(n), BEHAVIOURAL, f"Clicked {n} newsletter(s) about {focus}")
    # portal engagement last 90 days
    ps = ps.copy(); ps["start"] = pd.to_datetime(ps.session_start)
    p90 = ps[ps.start >= SNAPSHOT - dt.timedelta(days=90)].groupby("customer_id").size()
    for cid, st in state.items():
        st["portal_sessions_90d"] = int(p90.get(cid, 0))
    # contact history (fatigue) and last legacy actions
    hist = hist.copy(); hist["decided"] = pd.to_datetime(hist.decided_at)
    for cid, g in hist.groupby("customer_id"):
        sent = g[(g.delivery_status == "delivered") & (g.decided >= SNAPSHOT - dt.timedelta(days=30))]
        state[cid]["contacts_30d"] = int(len(sent))
        state[cid]["legacy_actions"] = [{"date": str(r.decided_at)[:10], "offer": r.offer_id, "channel": r.channel, "response": r.response}
                                        for r in g.sort_values("decided", ascending=False).head(5).itertuples()]
    for cid, st in state.items():
        st.setdefault("contacts_30d", 0); st.setdefault("legacy_actions", []); st.setdefault("failed_charges_30d", 0)
        st.setdefault("email_engagement", {"delivered": 0, "human_opens": 0, "machine_opens": 0, "clicks": 0})
        tone, why, inf, frm = tone_from_texts(st["texts"])
        st["tone"] = tone; st["tone_reason"] = why
        st["tone_sample"] = st["texts"][-1][:160] if st["texts"] else None
        st["recent_tickets"] = st["recent_tickets"][-5:][::-1]
    return state
