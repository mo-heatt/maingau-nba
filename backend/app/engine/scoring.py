import pandas as pd
from .constants import SETTINGS, CHANNELS, SIGNAL_LIFT, INTENT_LIFT, DRIVER_LABEL
from .signals import has, candidate_offers, service_case
from .utils import clv


def params(X):
    va = X["value_assumptions"]
    return {r.parameter: float(r.value) for r in va.itertuples()}


def acceptance_model(X):
    """p(accept) per offer x channel from the legacy action history (treated rows), smoothed toward the offer rate and global rate."""
    h = X["nba_action_history"]
    valid = pd.to_datetime(h.decided_at) + pd.Timedelta(days=14) <= pd.Timestamp("2026-09-30 23:59:00")
    h = h[valid]
    tr = h[(h.control_group == False) & (h.delivery_status == "delivered") & (h.consent_checked == True)]
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
        elif ch == "newsletter_email" and not s["consent"].get(cons, {}).get("doi"):
            why_not = "Newsletter double opt-in missing"
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


def score_customer(s, X, P, A, catalog, fcr_rate, settings=None):
    settings = settings or SETTINGS
    m, c = s["value"]["annual_margin"], s["value"]["cost_to_serve"]
    churn_now = current_churn(s, P)
    clv_now = clv(m, c, churn_now)
    parts = churn_parts(s, P)
    case = service_case(s)
    C, intent = candidate_offers(s)
    C = {oid:v for oid,v in C.items() if oid not in settings.get("offers_off", [])}
    chans = channel_options(s, A, P)
    for ch in chans:
        if ch["channel"] in settings.get("channels_off", []):
            ch.update(allowed=False, why_not="Channel disabled by marketing")
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
        if not prof:
            blocked.append("Profiling consent required for personal marketing")
        if settings.get("content_approvals", {}).get(oid, {}).get(s["tone"]) is False:
            blocked.append("Text is not approved for this tone")
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
    if svc_trigger and not has(s, "cancellation_pending") and "P-SV-01" not in settings.get("offers_off", []):
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
