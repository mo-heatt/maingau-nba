"""MAINGAU Next Best Action engine (MVP).

Pipeline per customer:
  1. state      – one row of signals per customer, built from the 15 tables
  2. candidates – offers whose target signal is present and that the customer doesn't hold
  3. rules      – consent per channel, profiling consent, exclusions (complaint, dunning, cancellation)
  4. scoring    – dCLV = p*(CLV_accept - CLV_now) + (1-p)*(CLV_reject - CLV_now) - contact_cost   (sheet clv_method)
  5. arbitration– best positive dCLV, contact limit, otherwise no action
  6. channel+tone+message – best allowed channel, Du/Sie from the customer's own words, approved template

Run:  python engine.py   -> writes out/engine_output.json
"""
import json, re, math, collections, datetime as dt
from pathlib import Path
import pandas as pd
from templates import TEMPLATES

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "out"
SNAPSHOT = dt.datetime(2026, 9, 30, 23, 59)
DECISION_DAY = dt.datetime(2026, 10, 1)

# ---------------------------------------------------------------- settings (editable, also steerable in the UI)
SETTINGS = {
    "contact_cap_30d": 3,          # max marketing contacts per customer in 30 days
    "min_dclv_eur": 0.0,           # drop actions below this expected gain
    "exclude_dunning_from_level": 1,
}
# Assumption (to validate): how much a strong target signal lifts acceptance vs. the legacy engine's broad targeting
SIGNAL_LIFT = {"strong": 2.0, "medium": 1.3, "weak": 1.0}
INTENT_LIFT = 1.5                   # human newsletter click / cart abandon on the same topic (needs profiling consent)

CHANNELS = {
    # channel: (consent needed, contact cost key, label)
    "portal_popup":   ("portal_app_personalisation", "contact_cost_popup_eur", "Portal pop-up"),
    "app_push":       ("portal_app_personalisation", "contact_cost_popup_eur", "App push"),
    "newsletter_email": ("newsletter_email", "contact_cost_email_eur", "Newsletter e-mail"),
    "email":          ("marketing_email", "contact_cost_email_eur", "Marketing e-mail"),
    "sms":            ("marketing_sms", "contact_cost_sms_eur", "SMS"),
    "outbound_call":  ("marketing_phone", "contact_cost_call_eur", "Outbound call"),
}
BEHAVIOURAL = "behavioural"   # signal class that needs profiling_analytics consent
CONTRACT = "contract"


def load():
    X = pd.read_excel(DATA / "maingau_nba_mockdata.xlsx", sheet_name=None)
    ev = [json.loads(l) for l in open(DATA / "event_stream_2026-10-01.jsonl", encoding="utf-8")]
    return X, ev


def ts(x):
    if x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NaT:
        return None
    try:
        return pd.Timestamp(x).to_pydatetime()
    except Exception:
        return None


def clv(margin, cost, churn, horizon=10, rate=0.06):
    churn = min(max(churn, 0.0), 0.99)
    return sum((margin - cost) * (1 - churn) ** (t - 1) / (1 + rate) ** t for t in range(1, horizon + 1))


# ---------------------------------------------------------------- 1. customer state
INFORMAL = [r"\bhi\b", r"\bhallo\b", r"\bhey\b", r"\bdu\b", r"\bdir\b", r"\bdich\b", r"\bdein\w*", r"\beuch\b", r"\bihr\b(?! \w+ (?:Sie|Ihnen))",
            r"\bkönnt\b", r"\bhabt\b", r"\bseid\b", r"danke dir", r"tschüss", r"\blg\b", r"\bviele grüße\b", r"\bnervig\b", r"\bsuper\b"]
FORMAL = [r"sehr geehrte", r"guten tag", r"\bsie\b", r"\bihnen\b", r"\bihr(?:e|en|em|er)?\b(?=.*\bsie\b)", r"mit freundlichen grüßen",
          r"auf wiederhören", r"\bbitte teilen sie\b", r"vielen dank"]


def tone_from_texts(texts):
    inf = frm = 0
    for t in texts:
        low = t.lower()
        inf += sum(len(re.findall(p, low)) for p in INFORMAL)
        frm += sum(len(re.findall(p, low)) for p in FORMAL)
    if inf == 0 and frm == 0:
        return "sie", "default (no own words from this customer)", 0, 0
    if inf > frm:
        return "du", f"informal words in own messages ({inf} informal vs {frm} formal)", inf, frm
    return "sie", f"formal words in own messages ({frm} formal vs {inf} informal)", inf, frm


def customer_lines(transcript):
    return [l.split(":", 1)[1] for l in str(transcript).split("\n") if l.lower().startswith("kunde:")]


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
        consent[r.customer_id][r.consent_type] = {"status": r.status, "updated_at": str(r.updated_at), "source": r.source}

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


# ---------------------------------------------------------------- 2.-5. decide
def params(X):
    va = X["value_assumptions"]
    return {r.parameter: float(r.value) for r in va.itertuples()}


def acceptance_model(X):
    """p(accept) per offer x channel from the legacy action history (treated rows), smoothed toward the offer rate and global rate."""
    h = X["nba_action_history"]
    tr = h[h.control_group == False]
    glob = tr.converted_within_14d.mean()
    by_ch = tr.groupby("channel").converted_within_14d.agg(["sum", "count"])
    ch_factor = {ch: ((r["sum"] + glob * 50) / (r["count"] + 50)) / glob for ch, r in by_ch.iterrows()}
    ch_factor["email"] = ch_factor.get("newsletter_email", 1.0)
    by_offer = tr.groupby("offer_id").converted_within_14d.agg(["sum", "count"])
    offer_rate = {o: (r["sum"] + glob * 20) / (r["count"] + 20) for o, r in by_offer.iterrows()}
    ctrl = h[h.control_group == True]
    uplift = []
    for o in sorted(h.offer_id.unique()):
        a = tr[tr.offer_id == o].converted_within_14d; b = ctrl[ctrl.offer_id == o].converted_within_14d
        uplift.append({"offer": o, "treated_n": int(len(a)), "treated_rate": round(float(a.mean()), 4), "control_n": int(len(b)),
                       "control_rate": round(float(b.mean()), 4) if len(b) else None,
                       "uplift": round(float(a.mean() - b.mean()), 4) if len(b) else None})
    return {"global": float(glob), "channel_factor": ch_factor, "offer_rate": offer_rate, "uplift": uplift,
            "overall": {"treated": round(float(tr.converted_within_14d.mean()), 4), "control": round(float(ctrl.converted_within_14d.mean()), 4),
                        "treated_n": int(len(tr)), "control_n": int(len(ctrl))}}


def has(s, key):
    return key in s["signals"]


def usable(s, key):
    """A signal can be used if it is contract data, or behavioural data with profiling consent."""
    if key not in s["signals"]:
        return False
    if s["signals"][key]["class"] == BEHAVIOURAL:
        return s["consent"].get("profiling_analytics", {}).get("status") == "granted"
    return True


def candidate_offers(s):
    """Offer -> (signal strength, why). Only offers whose target signal is present and that the customer doesn't hold."""
    H = s["holds"]; C = {}
    ev = lambda k: "; ".join(s["evidence"].get(k, []))
    elec = "electricity" in H
    if not elec and ("gas" in H or "mobile" in H or "autostrom" in H):
        C["P-EN-01"] = ("weak", "Customer has no electricity contract with MAINGAU")
    if usable(s, "guarantee_ending"):
        C["P-EN-02"] = ("strong", ev("guarantee_ending"))
    hp = [k for k in ("gas_meter_deregistered", "heat_pump_usage") if usable(s, k)] + (["dev"] if "dev_heat_pump" in H else [])
    if hp and "StromWärme" not in H:
        C["P-EN-03"] = ("strong", "; ".join(ev(k) for k in hp if k != "dev") or "Heat pump connected to HEMS")
    if usable(s, "smart_meter") and ("dev_hems_gateway" in H or "autostrom" in H or "dev_heat_pump" in H):
        C["P-EN-05"] = ("medium", ev("smart_meter") + " + HEMS/EV/heat pump in household")
    if (elec or "gas" in H) and "mobile" not in H:
        C["P-MO-01"] = ("weak", "Energy customer without a mobile contract")
    if usable(s, "data_limit_reached"):
        C["P-MO-02"] = ("strong", ev("data_limit_reached"))
    if usable(s, "household_more_than_sims"):
        C["P-MO-03"] = ("medium", ev("household_more_than_sims"))
    if elec or "mobile" in H:
        C["P-IN-01"] = ("weak", "No internet product with MAINGAU yet")
    gen = [k for k in ("gas_meter_deregistered", "wallbox_bought", "ev_driver") if usable(s, k)] + [d for d in ("dev_pv_inverter", "dev_wallbox", "dev_heat_pump") if d in H]
    if gen and "dev_hems_gateway" not in H:
        C["P-SL-01"] = ("medium", "Owns " + ", ".join(g.replace("dev_", "").replace("_", " ") for g in gen) + " but no HEMS")
    if "dev_hems_gateway" in H and "dev_home_battery" in H:
        C["P-SL-02"] = ("medium", "HEMS + home battery")
    if "dev_hems_gateway" in H and ("dev_wallbox" in H or usable(s, "wallbox_bought") or "autostrom" in H):
        C["P-SL-03"] = ("medium", "HEMS + electric car / wallbox")
    if "dev_pv_inverter" not in H and not any(h.startswith("order_Balkonkraftwerk") for h in H) and elec:
        C["P-SH-01"] = ("weak", "Electricity customer without solar")
    if "autostrom" in H and not usable(s, "wallbox_bought") and "dev_wallbox" not in H:
        C["P-SH-02"] = ("medium", "Drives an EV, charges only on the road (no wallbox)")
    if "gas" in H and not any("Thermostat" in h for h in H):
        C["P-SH-03"] = ("weak", "Gas heating customer")
    if usable(s, "shop_customer") and not any("Smart Plug" in h for h in H):
        C["P-SH-04"] = ("weak", "Existing shop customer")
    ev_sig = [k for k in ("wallbox_bought", "ev_home_charging") if usable(s, k)] + (["dev"] if "dev_wallbox" in H else [])
    if ev_sig and "autostrom" not in H:
        C["P-AS-01"] = ("strong", "; ".join(ev(k) for k in ev_sig if k != "dev") or "Wallbox connected to HEMS")
    # intent lifts (behavioural)
    intent = {}
    for focus, offers in {"clicked_energy": ["P-EN-01", "P-EN-02", "P-EN-03", "P-EN-05"], "clicked_mobile": ["P-MO-01", "P-MO-02", "P-MO-03"],
                          "clicked_shop": ["P-SH-01", "P-SH-02", "P-SH-03", "P-SH-04"], "clicked_smart_living": ["P-SL-01", "P-SL-02", "P-SL-03"],
                          "clicked_e_mobility": ["P-AS-01", "P-SH-02"], "clicked_heat_pump": ["P-EN-03", "P-SL-01"]}.items():
        if usable(s, focus):
            for o in offers:
                intent[o] = ev(focus)
    if s["consent"].get("profiling_analytics", {}).get("status") == "granted":
        for k, v in s.get("cart_intent", {}).items():
            intent[k] = v
    return C, intent


DRIVER_LABEL = {"open_complaint": "open complaint", "tickets_12m_ge2": "2+ tickets in 12 months", "csat_le2": "low satisfaction rating",
                "dunning_ge2": "dunning level 2+", "failed_charges_30d_ge3": "3+ failed charging sessions", "price_guarantee_ends_90d": "price guarantee ending"}

SERVICE_DRIVERS = [("open complaint", "open_complaint"), ("tickets in 12m", "tickets_12m_ge2"), ("low CSAT", "csat_le2"),
                   ("dunning level", "dunning_ge2"), ("failed charges", "failed_charges_30d_ge3")]


def service_case(s):
    """Reasons that make this an open service case (blocks sales)."""
    r = []
    if has(s, "open_complaint"): r.append("open complaint")
    dl = s["signals"].get("dunning_level", {"value": 0})["value"]
    if dl >= SETTINGS["exclude_dunning_from_level"]: r.append(f"dunning level {dl}")
    if has(s, "cancellation_pending"): r.append("cancellation received")
    return r


def churn_parts(s, P):
    drivers = s["value"]["churn_drivers"]
    parts = {}
    for d in drivers:
        dl = d.lower()
        if "price guarantee ends" in dl: parts["price_guarantee_ends_90d"] = P["price_guarantee_ends_90d"]
        elif "open complaint" in dl: parts["open_complaint"] = P["open_complaint"]
        elif "tickets in 12m" in dl: parts["tickets_12m_ge2"] = P["tickets_12m_ge2"]
        elif "low csat" in dl: parts["csat_le2"] = P["csat_le2"]
        elif "dunning level" in dl: parts["dunning_ge2"] = P["dunning_ge2"]
        elif "failed charges" in dl: parts["failed_charges_30d_ge3"] = P["failed_charges_30d_ge3"]
    # live state can add drivers the monthly CLV model hasn't seen yet (event replay)
    if has(s, "open_complaint"): parts.setdefault("open_complaint", P["open_complaint"])
    if s["signals"].get("dunning_level", {"value": 0})["value"] >= 2: parts.setdefault("dunning_ge2", P["dunning_ge2"])
    if has(s, "failed_charges"): parts.setdefault("failed_charges_30d_ge3", P["failed_charges_30d_ge3"])
    if has(s, "guarantee_ending"): parts.setdefault("price_guarantee_ends_90d", P["price_guarantee_ends_90d"])
    return parts


def current_churn(s, P):
    """Churn from the CLV model, plus drivers that appeared after the monthly CLV run (live events)."""
    base = s["value"]["churn"]
    for k, v in s.get("live_churn_add", {}).items():
        base += v
    if has(s, "cancellation_pending"):
        base = max(base, P["cancellation_pending"])
    return min(base, 0.95)


def channel_options(s, A, P):
    out = []
    prof = s["consent"].get("profiling_analytics", {}).get("status") == "granted"
    for ch, (cons, cost_key, label) in CHANNELS.items():
        status = s["consent"].get(cons, {}).get("status", "not_given")
        why_not = None
        if status != "granted":
            why_not = f"no consent ({cons}: {status})"
        elif ch == "portal_popup" and not s["portal_account"]:
            why_not = "no portal account"
        elif ch == "app_push" and not s["app_installed"]:
            why_not = "app not installed"
        eng = 1.0
        if prof and why_not is None:   # engagement-based channel ranking is profiling -> only with consent
            if ch == "portal_popup":
                eng = 1.3 if s["portal_sessions_90d"] >= 3 else (0.6 if s["portal_sessions_90d"] == 0 else 1.0)
            elif ch in ("newsletter_email", "email"):
                e = s["email_engagement"]
                if e["delivered"] >= 3:
                    rate = e["human_opens"] / e["delivered"]
                    eng = 0.5 + rate
        out.append({"channel": ch, "label": label, "allowed": why_not is None, "why_not": why_not,
                    "cost": P[cost_key], "factor": A["channel_factor"].get(ch, 1.0) * eng})
    return out


def score_customer(s, X, P, A, catalog, fcr_rate):
    m, c = s["value"]["annual_margin"], s["value"]["cost_to_serve"]
    churn_now = current_churn(s, P)
    clv_now = clv(m, c, churn_now)
    parts = churn_parts(s, P)
    case = service_case(s)
    C, intent = candidate_offers(s)
    chans = channel_options(s, A, P)
    allowed = [x for x in chans if x["allowed"]]
    prof = s["consent"].get("profiling_analytics", {}).get("status") == "granted"
    rows = []
    for oid, (strength, why) in C.items():
        p0 = catalog.loc[oid]
        add, eff, kind = float(p0.annual_margin_if_bought_eur or 0), float(0 if pd.isna(p0.churn_effect_if_bought) else p0.churn_effect_if_bought), p0.action_type
        if kind == "retention":
            churn_acc = churn_now - parts.get("price_guarantee_ends_90d", 0) + eff * 0  # value = removing the driver
            clv_acc = clv(m, c, churn_acc)
        elif kind == "one_off":
            clv_acc = clv(m, c, churn_now + eff) + add
        else:
            clv_acc = clv(m + add, c, churn_now + eff)
        clv_rej = clv(m, c, churn_now + P["contact_during_service_case"]) if case else clv_now
        base_p = A["offer_rate"].get(oid, A["global"]) * SIGNAL_LIFT[strength]
        lift_note = f"signal {strength} ×{SIGNAL_LIFT[strength]}"
        if oid in intent:
            base_p *= INTENT_LIFT; lift_note += f", intent ×{INTENT_LIFT} ({intent[oid]})"
        best = None; per_ch = []
        for ch in allowed:
            p = min(base_p * ch["factor"], 0.6)
            d = p * (clv_acc - clv_now) + (1 - p) * (clv_rej - clv_now) - ch["cost"]
            per_ch.append({"channel": ch["channel"], "p": round(p, 4), "dclv": round(d, 2)})
            if best is None or d > best["dclv"]:
                best = {"channel": ch["channel"], "label": ch["label"], "p": p, "dclv": d, "cost": ch["cost"]}
        blocked = []
        if case:
            blocked.append("Exclusion: " + ", ".join(case) + " – no sales content")
        if not allowed:
            blocked.append("No marketing channel with consent")
        rows.append({"offer": oid, "name": p0.product_name, "line": p0.business_line, "type": kind, "strength": strength, "why": why,
                     "p_base": round(base_p, 4), "lift_note": lift_note,
                     "clv_accept": round(clv_acc, 1), "clv_reject": round(clv_rej, 1),
                     "channel": best["channel"] if best else None, "channel_label": best["label"] if best else None,
                     "p": round(best["p"], 4) if best else round(base_p, 4),
                     "dclv": round(best["dclv"], 2) if best else round(base_p * (clv_acc - clv_now) + (1 - base_p) * (clv_rej - clv_now), 2),
                     "per_channel": per_ch, "blocked": blocked})
    # service action
    svc_parts = {k: v for k, v in parts.items() if k in ("open_complaint", "tickets_12m_ge2", "csat_le2", "dunning_ge2", "failed_charges_30d_ge3")}
    # a service fix is only proposed for an OPEN problem (catalog: open complaint, dunning, failed charging)
    svc_trigger = has(s, "open_complaint") or has(s, "failed_charges") or s["signals"].get("dunning_level", {"value": 0})["value"] >= 1
    if svc_trigger and not has(s, "cancellation_pending"):
        churn_acc = churn_now - sum(svc_parts.values())
        clv_acc = clv(m, c, max(churn_acc, 0.02)) - P["service_resolution_cost_eur"]
        p = fcr_rate
        d = p * (clv_acc - clv_now) - 0  # resolution cost already in clv_acc; a failed attempt changes nothing
        rows.append({"offer": "P-SV-01", "name": "Proactive service fix", "line": "service", "type": "service", "strength": "strong",
                     "why": "Fixing it removes churn drivers: " + ", ".join(DRIVER_LABEL.get(k, k) for k in svc_parts),
                     "p_base": round(p, 4), "lift_note": "p = first-contact resolution rate of complaints in ticket data",
                     "clv_accept": round(clv_acc, 1), "clv_reject": round(clv_now, 1), "channel": "agent_callback", "channel_label": "Service agent callback",
                     "p": round(p, 4), "dclv": round(d, 2), "per_channel": [], "blocked": []})
    rows.sort(key=lambda r: r["dclv"], reverse=True)
    return {"clv_now": round(clv_now, 1), "churn_now": round(churn_now, 3), "churn_parts": parts, "service_case": case,
            "channels": [{k: x[k] for k in ("channel", "label", "allowed", "why_not")} for x in chans], "candidates": rows,
            "profiling": prof}


def arbitrate(s, sc, settings=SETTINGS):
    """Pick the action. Same logic is mirrored in the web app so marketing can change the settings."""
    log = []
    if has(s, "cancellation_pending"):
        return {"action": "human_review", "title": "Hand to retention team", "reason": "Cancellation received – a person decides, no automated contact.", "log": ["Rule: cancellation pending → human review"]}
    svc = next((r for r in sc["candidates"] if r["offer"] == "P-SV-01"), None)
    open_sales = [r for r in sc["candidates"] if r["offer"] != "P-SV-01" and not r["blocked"]]
    if sc["service_case"]:
        log.append("Rule: " + ", ".join(sc["service_case"]) + " → sales content blocked")
    viable = [r for r in open_sales if r["dclv"] > settings["min_dclv_eur"]]
    if svc and svc["dclv"] > settings["min_dclv_eur"] and (sc["service_case"] or not viable or svc["dclv"] >= viable[0]["dclv"]):
        return {"action": "offer", "pick": svc, "title": svc["name"], "log": log + [f"Picked service fix: +€{svc['dclv']:.0f} expected"],
                "reason": f"{svc['why']}. Fix first: expected +€{svc['dclv']:.0f} customer value."}
    if sc["service_case"]:
        return {"action": "none", "title": "No contact", "reason": "Open service case and no service fix worth doing – leave the customer alone.", "log": log}
    if not viable:
        best = open_sales[0] if open_sales else None
        why = (f"Best option ({best['name']}) is only worth €{best['dclv']:.2f} – not worth a contact." if best else "No relevant offer for this customer.")
        return {"action": "none", "title": "No action", "reason": why, "log": log + ["No candidate above minimum value"]}
    if s["contacts_30d"] >= settings["contact_cap_30d"]:
        return {"action": "wait", "title": "Wait (contact limit)", "reason": f"Already contacted {s['contacts_30d']}× in 30 days (limit {settings['contact_cap_30d']}). Next best: {viable[0]['name']}.",
                "pick": viable[0], "log": log + ["Rule: contact limit reached"]}
    r = viable[0]
    return {"action": "offer", "pick": r, "title": r["name"], "log": log + [f"Picked {r['offer']} via {r['channel_label']}: +€{r['dclv']:.2f}"],
            "reason": f"{r['why']}. Via {r['channel_label']} (p={r['p']*100:.1f}%) → expected +€{r['dclv']:.2f}."}


def message(s, decision):
    pick = decision.get("pick")
    if not pick:
        return None
    t = s["tone"]
    subj, body = TEMPLATES[pick["offer"]][t]
    g = s["signals"].get("guarantee_ending", {}).get("value")
    if g:
        d = dt.datetime.strptime(g, "%Y-%m-%d")
        gt = (f"am {d:%d.%m.%Y} aus" if d >= DECISION_DAY else f"seit dem {d:%d.%m.%Y} nicht mehr")
    else:
        gt = "bald aus"
    return {"tone": t, "subject": subj, "body": body.replace("{guarantee_text}", gt)}


# ---------------------------------------------------------------- run everything
def run():
    X, events = load()
    P = params(X)
    A = acceptance_model(X)
    catalog = X["product_catalog"].set_index("product_id")
    comp = X["service_interactions"]; comp = comp[(comp.category == "complaint") & (comp.status == "closed")]
    fcr_rate = float(comp.first_contact_resolution.mean())
    state = build_state(X)
    out = {}
    for cid, s in state.items():
        sc = score_customer(s, X, P, A, catalog, fcr_rate)
        dec = arbitrate(s, sc)
        out[cid] = (sc, dec, message(s, dec))
    return X, events, P, A, catalog, fcr_rate, state, out


if __name__ == "__main__":
    from export import export
    export(*run())
