"""Steps 3–5: eligibility rules, dCLV scoring, ranking, channel and tone.

Formula (sheet clv_method):
  dCLV = p * (CLV_accept - CLV_now) + (1 - p) * (CLV_reject - CLV_now) - contact_cost
Hard rules (consent, exclusions) run before ranking.
"""
import hashlib
from collections import defaultdict

from .content import detect_tone, message

# ---------------------------------------------------------------- settings
# Our own assumptions (not in the data). Shown in the app so they can be challenged.
OUR_ASSUMPTIONS = {
    "p_service_fix": 0.6,          # chance a proactive service call resolves the case
    "p_cancellation_reversed": 0.25,  # chance a callback reverses a cancellation
    "churn_if_cancellation_reversed": 0.30,
    "max_marketing_contacts_30d": 3,  # fatigue limit (ask Caro)
    "control_group_share": 0.10,
    "prior_strength": 20,          # how strongly small history cells shrink to the offer average
}

CHANNELS = {
    # channel: (consent needed, cost parameter)
    "newsletter_email": ("newsletter_email", "contact_cost_email_eur"),
    "email": ("marketing_email", "contact_cost_email_eur"),
    "portal_popup": ("portal_app_personalisation", "contact_cost_popup_eur"),
    "app_push": ("portal_app_personalisation", "contact_cost_popup_eur"),
    "sms": ("marketing_sms", "contact_cost_sms_eur"),
    "outbound_call": ("marketing_phone", "contact_cost_call_eur"),
}
CHANNEL_LABEL = {
    "newsletter_email": "Newsletter", "email": "E-mail", "portal_popup": "Portal pop-up",
    "app_push": "App push", "sms": "SMS", "outbound_call": "Phone call", "service_callback": "Service callback",
}
SERVICE_DRIVERS = {  # flag -> churn parameter removed by a service fix
    "open_complaint": "open_complaint", "many_tickets": "tickets_12m_ge2", "low_csat": "csat_le2",
    "dunning2": "dunning_ge2", "failed_charges": "failed_charges_30d_ge3",
}
LINE_OF = {"energy": "energy", "mobile": "mobile", "internet": "internet", "smart_living": "smart_living",
           "shop": "shop", "e_mobility": "e_mobility", "service": "service"}


def clv(margin, cost, churn, a):
    churn = min(max(churn, 0.01), 0.95)
    r, n = a["discount_rate"], int(a["horizon_years"])
    return sum((margin - cost) * (1 - churn) ** (t - 1) / (1 + r) ** t for t in range(1, n + 1))


# ---------------------------------------------------------------- p(accept) from history
class AcceptModel:
    """Conversion rate by offer x channel x tone, shrunk toward the offer rate, then the global rate."""

    def __init__(self, history, k):
        self.k = k
        g = [0, 0]
        off = defaultdict(lambda: [0, 0])
        cell = defaultdict(lambda: [0, 0])
        ctrl = defaultdict(lambda: [0, 0])
        for h in history:
            conv = 1 if h["converted_within_14d"] else 0
            if h["control_group"]:
                ctrl[h["offer_id"]][0] += conv
                ctrl[h["offer_id"]][1] += 1
                continue
            g[0] += conv; g[1] += 1
            off[h["offer_id"]][0] += conv; off[h["offer_id"]][1] += 1
            cell[(h["offer_id"], h["channel"], h["tonality"])][0] += conv
            cell[(h["offer_id"], h["channel"], h["tonality"])][1] += 1
        self.g = g[0] / g[1]
        self.off, self.cell, self.ctrl = off, cell, ctrl

    def offer_rate(self, o):
        c, n = self.off.get(o, (0, 0))
        return (c + self.k * self.g) / (n + self.k)

    def p(self, offer, channel, tone):
        ch = "newsletter_email" if channel == "email" else channel
        base = self.offer_rate(offer)
        c, n = self.cell.get((offer, ch, tone), (0, 0))
        return (c + self.k * base) / (n + self.k), n

    def uplift_table(self):
        rows = []
        for o in sorted(set(self.off) | set(self.ctrl)):
            tc, tn = self.off.get(o, (0, 0))
            cc, cn = self.ctrl.get(o, (0, 0))
            rows.append({"offer": o, "treated_n": tn, "treated_conv": tc, "control_n": cn, "control_conv": cc,
                         "treated_rate": tc / tn if tn else 0, "control_rate": cc / cn if cn else 0})
        return rows


# ---------------------------------------------------------------- eligibility: which offers make sense at all
def offer_signal(oid, s):
    """Return a short reason string if the customer shows the signal for this offer, else None."""
    f = s["flags"]
    lines = s["lines"]
    bought = s.get("bought", set())
    if oid == "P-EN-01":
        return "charges with Autostrom but buys household power elsewhere" if "has_electricity" not in f and lines else None
    if oid == "P-EN-02":
        return s["evidence"].get("guarantee_ending") if "guarantee_ending" in f else None
    if oid == "P-EN-03":
        return s["evidence"]["heat_pump_signal"] if "heat_pump_signal" in f and "has_heatpump_tariff" not in f else None
    if oid == "P-EN-04":
        return None  # gas heating is not visible in the data
    if oid == "P-EN-05":
        if "smart_meter" in f and ({"has_hems", "ev_signal", "heat_pump_signal"} & f):
            return "has a smart meter plus HEMS / EV / heat pump"
        return None
    if oid == "P-MO-01":
        return "energy customer without a mobile contract" if "energy" in lines and "mobile" not in lines else None
    if oid == "P-MO-02":
        return s["evidence"].get("data_limit") if "data_limit" in f else None
    if oid == "P-MO-03":
        if "mobile" in lines and s["household_size"] > s["sim_count"]:
            return f"{s['household_size']} people in household, {s['sim_count']} SIM"
        return None
    if oid == "P-IN-01":
        return "energy or mobile customer without internet" if lines & {"energy", "mobile"} else None
    if oid == "P-SL-01":
        if "has_hems" not in f and ({"has_pv", "heat_pump_signal", "ev_signal"} & f):
            k = next(x for x in ("has_pv", "heat_pump_signal", "ev_signal") if x in f)
            return s["evidence"].get(k, k)
        return None
    if oid == "P-SL-02":
        return "has HEMS and a home battery" if {"has_hems", "has_battery"} <= f else None
    if oid == "P-SL-03":
        return "has HEMS and an EV / wallbox" if "has_hems" in f and ({"has_wallbox", "ev_signal"} & f) else None
    if oid == "P-SH-01":
        return "electricity customer without own solar" if "has_electricity" in f and "has_pv" not in f else None
    if oid == "P-SH-02":
        return s["evidence"]["ev_signal"] + ", no wallbox yet" if "ev_signal" in f and "has_wallbox" not in f else None
    if oid == "P-SH-03":
        return "gas customer without smart thermostats" if "has_gas" in f and "has_thermostats" not in f else None
    if oid == "P-SH-04":
        return "uses the portal, no smart plugs yet" if s["portal_account"] and "has_smart_plugs" not in f and lines else None
    if oid == "P-AS-01":
        return s["evidence"]["ev_signal"] + ", no Autostrom card" if "ev_signal" in f and "has_autostrom" not in f else None
    if oid == "P-SV-01":
        for k in ("open_complaint", "cancellation", "dunning", "failed_charges", "open_ticket", "hems_offline"):
            if k in f:
                return s["evidence"].get(k, k)
        return None
    return None


def service_case(s):
    """Exclusions from the brief: dunning, open complaints or cancellations block sales content.
    Our addition: 3+ failed charging sessions and an upset customer also count (brief's own example)."""
    f = s["flags"]
    hits = [k for k in ("open_complaint", "dunning", "cancellation", "failed_charges", "upset") if k in f]
    return hits


def channel_ok(ch, s):
    need = CHANNELS[ch][0]
    if s["consent"].get(need) != "granted":
        return False, f"no {need} consent"
    if ch == "portal_popup" and not s["portal_account"]:
        return False, "no portal account"
    if ch == "app_push" and not s["app_installed"]:
        return False, "app not installed"
    return True, ""


def engagement(ch, s, avg, profiling):
    """How reachable this customer is on a channel. Only used with profiling consent."""
    if not profiling:
        return 1.0
    if ch in ("newsletter_email", "email"):
        d = s.get("nl_delivered", 0)
        if not d:
            return 1.0
        rate = s.get("nl_human_opens", 0) / d
        return min(2.0, max(0.3, rate / avg["open_rate"])) if avg["open_rate"] else 1.0
    if ch == "portal_popup":
        n = s.get("portal_sessions_90d", 0)
        return 0.2 if n == 0 else min(2.0, max(0.3, n / avg["portal"]))
    return 1.0


# ---------------------------------------------------------------- scoring
def score(oid, prod, s, a, p):
    """dCLV for one offer at acceptance probability p (contact cost added by caller)."""
    m, c, ch = s["margin"], s["cost"], s["churn"]
    now = clv(m, c, ch, a)
    kind = prod["action_type"]
    gain = float(prod["annual_margin_if_bought_eur"] or 0)
    eff = float(prod["churn_effect_if_bought"] or 0)
    line = prod["business_line"]
    if kind in ("sales", "upsell"):
        extra_cost = a["base_per_business_line_eur"] if (kind == "sales" and line not in s["lines"]) else 0
        after = clv(m + gain, c + extra_cost, ch + eff, a)
    elif kind == "one_off":
        after = clv(m, c, ch + eff, a) + gain / (1 + a["discount_rate"])
    elif kind == "retention":
        after = clv(m, c, ch - a["price_guarantee_ends_90d"], a)
    elif kind == "service":
        if "cancellation" in s["flags"]:
            p = OUR_ASSUMPTIONS["p_cancellation_reversed"]
            after = clv(m, c, OUR_ASSUMPTIONS["churn_if_cancellation_reversed"], a)
        else:
            removed = 0.0
            f = set(s["flags"])
            if s.get("dunning_level", 0) >= 2:
                f.add("dunning2")
            for flag_, param in SERVICE_DRIVERS.items():
                if flag_ in f:
                    removed += a[param]
            after = clv(m, c, ch - removed, a)
        after -= a["service_resolution_cost_eur"]
    else:
        after = now
    reject = now
    if kind != "service" and ({"open_complaint", "dunning"} & s["flags"] or "failed_charges" in s["flags"]):
        reject = clv(m, c, ch + a["contact_during_service_case"], a)
    return p * (after - now) + (1 - p) * (reject - now), p, now


def control_member(cid, share):
    h = int(hashlib.sha256(cid.encode()).hexdigest(), 16) % 1000
    return h < share * 1000


def decide(s, catalog, a, model, avg, settings=None):
    """Full decision for one customer, with every candidate and the reason it won or lost."""
    st = dict(OUR_ASSUMPTIONS)
    if settings:
        st.update(settings)
    tone, tone_why = detect_tone(s["texts"])
    profiling = s["consent"].get("profiling_analytics") == "granted"
    blocked_by_case = service_case(s)
    fatigue = s.get("contacts_30d", 0) >= st["max_marketing_contacts_30d"]
    cands = []
    for oid, prod in catalog.items():
        why = offer_signal(oid, s)
        if why is None:
            continue
        kind = prod["action_type"]
        block = None
        btype = None
        if kind == "service":
            # service is a contractual contact by a human agent: no marketing consent needed
            p0 = st["p_service_fix"]
            v, p, _ = score(oid, prod, s, a, p0)
            v -= a["contact_cost_call_eur"]
            cands.append({"offer": oid, "name": prod["product_name"], "kind": kind, "channel": "service_callback",
                          "p": round(p, 3), "value": round(v, 2), "signal": why, "blocked": None, "block_type": None})
            continue
        if blocked_by_case:
            block, btype = "service case open: " + ", ".join(blocked_by_case), "case"
        elif kind != "retention" and not profiling:
            block, btype = "no profiling consent: no personalised offers", "profiling"
        elif fatigue:
            block, btype = f"contact limit reached ({s.get('contacts_30d', 0)} contacts in 30 days)", "fatigue"
        best = None
        for ch in CHANNELS:
            ok, _ = channel_ok(ch, s)
            if not ok:
                continue
            p_base, n = model.p(oid, ch, tone)
            p = min(0.9, p_base * engagement(ch, s, avg, profiling) * s["intent_boost"].get(oid, 1.0))
            v, p, _ = score(oid, prod, s, a, p)
            v -= a[CHANNELS[ch][1]]
            if best is None or v > best["value"]:
                best = {"offer": oid, "name": prod["product_name"], "kind": kind, "channel": ch, "p": round(p, 3),
                        "value": round(v, 2), "signal": why, "history_n": n}
        if best is None:
            # still show the economics, but there is no allowed channel
            v, p, _ = score(oid, prod, s, a, model.offer_rate(oid))
            best = {"offer": oid, "name": prod["product_name"], "kind": kind, "channel": None, "p": round(p, 3),
                    "value": round(v, 2), "signal": why}
            if not block:
                block, btype = "no marketing channel with consent", "channel"
        best["blocked"] = block
        best["block_type"] = btype
        cands.append(best)

    cands.sort(key=lambda x: x["value"], reverse=True)
    allowed = [c for c in cands if not c["blocked"] and c["value"] > 0]
    chosen = allowed[0] if allowed else None
    in_control = control_member(s["id"], st["control_group_share"])
    decision = {
        "action": chosen["offer"] if chosen else None,
        "name": chosen["name"] if chosen else "No action",
        "kind": chosen["kind"] if chosen else "none",
        "channel": chosen["channel"] if chosen else None,
        "tone": tone,
        "tone_why": tone_why,
        "value": chosen["value"] if chosen else 0.0,
        "p": chosen["p"] if chosen else 0.0,
        "control_group": in_control,
        "reason": reason(chosen, s, cands, blocked_by_case, profiling),
        "message": message(chosen["offer"], tone) if chosen else None,
        "checks": checks(s, profiling, blocked_by_case, fatigue, chosen),
    }
    return decision, cands


def reason(ch, s, cands, case, profiling):
    if ch is None:
        if not cands:
            return "No offer fits this customer's situation; do nothing."
        if not profiling:
            return "No profiling consent and no service case: no personalised action."
        return "Every possible action is blocked or would lower customer value; do nothing."
    if ch["kind"] == "service":
        lost = [c for c in cands if c["kind"] != "service"]
        tail = f" A sales offer now would score {min(c['value'] for c in lost):+.0f} € or be blocked." if lost else ""
        return f"Fix first: {ch['signal']}. Resolving it is worth {ch['value']:+.0f} € in customer value.{tail}"
    return (f"{ch['signal'][:1].upper() + ch['signal'][1:]}. {ch['name']} via {CHANNEL_LABEL[ch['channel']]} "
            f"has the highest expected gain: {ch['value']:+.2f} € (acceptance {ch['p']:.0%}).")


def checks(s, profiling, case, fatigue, chosen):
    c = s["consent"]
    out = [
        {"rule": "Channel consent", "ok": chosen is None or chosen["kind"] == "service" or
         c.get(CHANNELS[chosen["channel"]][0]) == "granted",
         "detail": ", ".join(k.replace("_", " ") for k, v in c.items() if v == "granted") or "none granted"},
        {"rule": "Profiling consent", "ok": profiling, "detail": c.get("profiling_analytics", "unknown")},
        {"rule": "No open complaint", "ok": "open_complaint" not in s["flags"], "detail": s["evidence"].get("open_complaint", "none")},
        {"rule": "No dunning", "ok": "dunning" not in s["flags"], "detail": s["evidence"].get("dunning", "none")},
        {"rule": "No cancellation", "ok": "cancellation" not in s["flags"], "detail": s["evidence"].get("cancellation", "none")},
        {"rule": "Contact limit", "ok": not fatigue, "detail": f"{s.get('contacts_30d', 0)} contacts in last 30 days"},
    ]
    return out
