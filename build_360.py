"""Data for the "360 new" tab: joins all source systems into one profile + one cross-channel timeline per customer."""
import json, math, collections
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
DATA = ROOT / "data"
SNAPSHOT = pd.Timestamp("2026-09-30 23:59")
TL_MAX = 50        # timeline entries per customer (newest first)
TXT = 160          # characters of free text per entry


def nn(x):
    """NaN/NaT -> None, numpy scalars -> python."""
    if x is None or x is pd.NaT:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if hasattr(x, "item"):
        return x.item()
    return x


def t16(x):
    x = nn(x)
    if x is None:
        return None
    try:
        return str(pd.Timestamp(x))[:16]
    except Exception:
        return None


def d10(x):
    s = t16(x)
    return s[:10] if s else None


def cut(s, n=TXT):
    s = nn(s)
    if not s:
        return ""
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 1] + "…"


def future(x):
    try:
        return pd.Timestamp(x) > SNAPSHOT
    except Exception:
        return False


def rnd(x, d=2):
    x = nn(x)
    return round(float(x), d) if x is not None else None


def build():
    X = pd.read_excel(DATA / "maingau_nba_mockdata.xlsx", sheet_name=None)
    events = [json.loads(l) for l in open(DATA / "event_stream_2026-10-01.jsonl", encoding="utf-8")]
    offers = dict(zip(X["product_catalog"].product_id, X["product_catalog"].product_name))
    camp = {r.campaign_id: r for r in X["newsletter_campaigns"].itertuples()}

    P = {cid: {"tl": []} for cid in X["customer_master"].customer_id}
    tl = lambda cid, at, src, title, detail="", flag="": P[cid]["tl"].append([at, src, title, detail, flag]) if cid in P and at else None

    for r in X["customer_master"].itertuples():
        P[r.customer_id].update(type=r.customer_type, plz=str(nn(r.postal_code_prefix) or ""))
        tl(r.customer_id, t16(r.customer_since), "crm", "Became a MAINGAU customer")

    # contracts
    for r in X["energy_contracts"].itertuples():
        p = P[r.customer_id]
        p.setdefault("energy", []).append({
            "com": r.commodity, "tariff": r.tariff, "st": r.status, "start": d10(r.start_date), "guar": d10(r.price_guarantee_until),
            "notice": nn(r.notice_period_weeks), "kwh": nn(r.annual_consumption_kwh), "price": rnd(r.energy_price_eur_kwh, 4),
            "inst": rnd(r.monthly_installment_eur), "meter": r.meter_type, "feed": bool(nn(r.feed_in_meter)), "pay": r.payment_method,
            "dun": int(nn(r.dunning_level) or 0), "cancel": d10(r.cancellation_received_at), "read": d10(r.last_meter_reading_at)})
        tl(r.customer_id, t16(r.start_date), "contract", f"{r.tariff} ({r.commodity}) started")
        if nn(r.cancellation_received_at):
            tl(r.customer_id, t16(r.cancellation_received_at), "contract", f"Cancellation received: {r.tariff}", "", "bad")
        if nn(r.meter_deregistered_at):
            tl(r.customer_id, t16(r.meter_deregistered_at), "contract", "Gas meter deregistered", "", "bad")
        if nn(r.price_guarantee_until):
            tl(r.customer_id, t16(r.price_guarantee_until), "contract", f"Price guarantee {'ends' if future(r.price_guarantee_until) else 'ended'}: {r.tariff}", "", "warn")
    for r in X["mobile_contracts"].itertuples():
        P[r.customer_id].setdefault("mobile", []).append({
            "plan": r.plan, "gb": nn(r.data_volume_gb), "fee": rnd(r.monthly_fee_eur), "sims": nn(r.sim_count), "st": r.status, "start": d10(r.start_date),
            "minEnd": d10(r.min_term_end), "used": rnd(r.avg_data_used_gb_3m, 1), "hits": nn(r.data_limit_reached_3m), "roam": nn(r.roaming_days_3m), "esim": bool(nn(r.esim))})
        tl(r.customer_id, t16(r.start_date), "contract", f"Mobile {r.plan} started")
        if nn(r.min_term_end):
            tl(r.customer_id, t16(r.min_term_end), "contract", f"Mobile minimum term {'ends' if future(r.min_term_end) else 'ended'}")
    for r in X["autostrom_contracts"].itertuples():
        P[r.customer_id].setdefault("auto", []).append({
            "st": r.status, "start": d10(r.start_date), "car": f"{nn(r.car_brand) or ''} {nn(r.car_model) or ''}".strip(), "batt": nn(r.battery_kwh),
            "dcmax": nn(r.max_dc_kw), "cards": nn(r.charge_cards), "app": bool(nn(r.app_user)), "ac": rnd(r.ac_price_eur_kwh, 2), "dc": rnd(r.dc_price_eur_kwh, 2)})
        tl(r.customer_id, t16(r.start_date), "contract", "Autostrom started", P[r.customer_id]["auto"][-1]["car"])
        if nn(r.cancelled_at):
            tl(r.customer_id, t16(r.cancelled_at), "contract", "Autostrom cancelled", "", "bad")

    # charging: summary + the latest and failed sessions on the timeline
    cs = X["charge_sessions"].assign(started_at=pd.to_datetime(X["charge_sessions"].started_at, errors="coerce")).sort_values("started_at")
    for cid, g in cs.groupby("customer_id"):
        if cid not in P:
            continue
        ok = g[g.session_status == "completed"]
        P[cid]["charge"] = {"n": len(g), "kwh": rnd(ok.energy_kwh.sum(), 0), "eur": rnd(ok.amount_eur.sum(), 0),
                            "dc": rnd((g.charge_type == "DC").mean(), 2), "fail": int((g.session_status != "completed").sum()),
                            "abroad": int((g.country != "DE").sum()), "last": d10(g.started_at.max()),
                            "cities": [c for c, _ in collections.Counter(g.location_city.dropna()).most_common(3)]}
        for r in g.tail(3).itertuples():
            tl(cid, t16(r.started_at), "charge", f"{r.charge_type} charge, {rnd(r.energy_kwh, 1)} kWh", f"{nn(r.location_city) or ''} · {r.session_status}", "bad" if r.session_status != "completed" else "")
        for r in g[g.session_status != "completed"].iloc[:-3].tail(3).itertuples():
            tl(cid, t16(r.started_at), "charge", f"{r.charge_type} charge {r.session_status}", cut(r.failure_reason), "bad")

    # HEMS
    for r in X["hems_devices"].itertuples():
        P[r.customer_id].setdefault("hems", {"dev": []})["dev"].append([r.device_type, nn(r.manufacturer), r.connection_status, t16(r.last_seen_at)])
        tl(r.customer_id, t16(r.activated_at), "hems", f"{r.device_type.replace('_', ' ').title()} connected", nn(r.manufacturer) or "")
    ht = X["hems_telemetry_daily"].assign(date=pd.to_datetime(X["hems_telemetry_daily"].date, errors="coerce"))
    for cid, g in ht.sort_values("date").groupby("customer_id"):
        if cid not in P:
            continue
        h = P[cid].setdefault("hems", {"dev": []})
        h["days"] = [d10(d) for d in g.date]
        for k, col in [("pv", "pv_generation_kwh"), ("use", "household_consumption_kwh"), ("imp", "grid_import_kwh"), ("exp", "grid_export_kwh"), ("ev", "ev_charging_kwh"), ("hp", "heat_pump_kwh")]:
            h[k] = [rnd(v, 1) for v in g[col]]
        h["self"] = rnd(g.self_consumption_rate.mean(), 2)

    # shop
    so = X["shop_orders"].assign(order_created_at=pd.to_datetime(X["shop_orders"].order_created_at, errors="coerce"))
    for cid, g in so.dropna(subset=["customer_id"]).groupby("customer_id"):
        if cid not in P:
            continue
        P[cid]["shop"] = {"n": int(g.order_id.nunique()), "eur": rnd(g.line_value_eur.sum(), 0), "last": d10(g.order_created_at.max())}
        for r in g.itertuples():
            tl(cid, t16(r.order_created_at), "shop", f"Ordered {r.product_name}", f"€{nn(r.line_value_eur) or 0:,.0f} · {r.order_channel} · {r.order_status}", "bad" if r.order_status in ("cancelled", "returned") else "")

    # newsletter
    for cid, g in X["newsletter_performance"].groupby("customer_id"):
        if cid not in P:
            continue
        P[cid]["nl"] = {"sent": len(g), "open": int(g.opened_at.notna().sum()), "click": int(g.clicked_at.notna().sum()),
                        "conv": int(g.converted_within_7d.fillna(False).astype(bool).sum()), "unsub": bool(g.unsubscribed.fillna(False).astype(bool).any())}
        for r in g.itertuples():
            c = camp.get(r.campaign_id)
            subj = c.subject_line if c is not None else r.campaign_id
            if nn(r.clicked_at):
                tl(cid, t16(r.clicked_at), "nl", f"Clicked newsletter: {subj}", cut(r.click_target), "good")
            elif nn(r.opened_at):
                tl(cid, t16(r.opened_at), "nl", f"Opened newsletter: {subj}")
            if nn(r.unsubscribed):
                tl(cid, t16(r.opened_at) or (t16(c.sent_at) if c is not None else None), "nl", "Unsubscribed from newsletter", "", "bad")

    # portal
    since90 = SNAPSHOT - pd.Timedelta(days=90)
    ps = X["portal_sessions"].assign(session_start=pd.to_datetime(X["portal_sessions"].session_start, errors="coerce"))
    for cid, g in ps.sort_values("session_start").groupby("customer_id"):
        if cid not in P:
            continue
        r90 = g[g.session_start >= since90]
        P[cid]["portal"] = {"n": len(g), "n90": len(r90), "app": rnd((g.client == "app").mean(), 2), "last": d10(g.session_start.max()),
                            "banner": int(g.offer_banner_shown.fillna(False).astype(bool).sum())}
        for r in g.tail(3).itertuples():
            tl(cid, t16(r.session_start), "portal", f"Portal session ({r.client})", f"{str(nn(r.pages_viewed) or '').replace('|', ', ')} · {round((nn(r.duration_s) or 0) / 60)} min")

    # service, calls, agent feedback
    for cid, g in X["service_interactions"].groupby("customer_id"):
        if cid not in P:
            continue
        P[cid]["svc"] = {"n": len(g), "open": int((g.status != "closed").sum()), "csat": rnd(g.csat_1to5.mean(), 1),
                         "fcr": rnd(g.first_contact_resolution.dropna().astype(bool).mean(), 2) if g.first_contact_resolution.notna().any() else None,
                         "cost": rnd(g.handling_cost_eur.sum() + g.goodwill_eur.fillna(0).sum(), 0)}
        for r in g.itertuples():
            tl(cid, t16(r.created_at), "svc", f"Ticket: {str(r.category).replace('_', ' ')} via {str(r.channel).replace('_', ' ')}",
               cut(nn(r.message_text) or nn(r.call_note)), "bad" if r.status != "closed" else "")
    for r in X["call_transcripts"].itertuples():
        tl(r.customer_id, t16(r.call_started_at), "call", f"Call, {round((nn(r.duration_s) or 0) / 60)} min", cut(r.transcript))
    for r in X["service_nba_feedback"].itertuples():
        tl(r.customer_id, t16(r.shown_at), "agent", f"Agent suggestion: {offers.get(r.suggested_offer_id, r.suggested_offer_id)}",
           f"{str(r.agent_action).replace('_', ' ')}{' · ' + str(r.customer_reaction).replace('_', ' ') if nn(r.customer_reaction) else ''}",
           "good" if nn(r.converted_within_14d) else "")

    # earlier NBA (legacy rule engine) actions
    for r in X["nba_action_history"].itertuples():
        tl(r.customer_id, t16(r.decided_at), "nba", f"Campaign: {offers.get(r.offer_id, r.offer_id)}",
           f"{str(r.channel).replace('_', ' ')} · {r.response}{' · converted' if nn(r.converted_within_14d) else ''}",
           "good" if nn(r.converted_within_14d) else ("" if r.response in ("clicked", "viewed", "held_out") else "muted"))

    # consent changes
    for r in X["consent_status"].itertuples():
        tl(r.customer_id, t16(r.updated_at), "consent", f"Consent {str(r.consent_type).replace('_', ' ')}: {r.status}", cut(r.source),
           "bad" if r.status == "withdrawn" else "")

    # live events (1 October)
    for e in events:
        pl = e.get("payload") or {}
        detail = " · ".join(f"{k.replace('_', ' ')}: {v}" for k, v in pl.items() if not isinstance(v, (dict, list)))
        bad = e["event_type"] in ("contract_cancellation_received", "charge_session_failed", "hems_device_offline", "dunning_level_changed", "ticket_created", "gas_meter_deregistration_received", "cart_abandoned")
        tl(e.get("customer_id"), e["occurred_at"][:16], "live", e["event_type"].replace("_", " ").capitalize(), cut(detail), "bad" if bad else "")

    for p in P.values():
        p["tl"].sort(key=lambda x: x[0], reverse=True)
        p["tl"] = p["tl"][:TL_MAX]

    src = [{k: nn(v) for k, v in r.items()} for r in X["sources"].to_dict("records")]
    return P, src


if __name__ == "__main__":
    P, src = build()
    blob = json.dumps(P, ensure_ascii=False, separators=(",", ":"))
    print("customers", len(P), "| KB", len(blob) // 1024, "| avg timeline", sum(len(p["tl"]) for p in P.values()) / len(P))
