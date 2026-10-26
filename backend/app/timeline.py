"""One timeline per customer that joins every source system, from becoming a customer to today.

Ported from the "360 new" prototype (feature/360-new). Each entry names the system it came from,
so a service agent sees contracts, tickets, calls, campaigns, shop, charging, portal, newsletter,
consent and the live event stream in one place. Read-only: it never changes the source records.
"""
import json
import math
from collections import defaultdict

import pandas as pd

from . import database as db

SNAPSHOT = pd.Timestamp("2026-09-30 23:59")
DETAIL_CHARS = 160
# Long streams are cut to the latest few per customer; milestones are always kept.
LATEST = {"charge": 3, "portal": 3}

SOURCES = {
    "crm": "CRM", "contract": "Contracts", "svc": "Service", "call": "Calls", "agent": "Agent assist",
    "nba": "Campaigns", "nl": "Newsletter", "shop": "Shop", "charge": "Charging", "hems": "HEMS",
    "portal": "Portal", "consent": "Consent", "live": "Live events",
}
BAD_EVENTS = {"contract_cancellation_received", "charge_session_failed", "hems_device_offline", "dunning_level_changed",
              "ticket_created", "gas_meter_deregistration_received", "cart_abandoned"}


def _nn(x):
    if x is None or x is pd.NaT:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return x.item() if hasattr(x, "item") else x


def _ts(x):
    x = _nn(x)
    if x is None:
        return None
    try:
        return str(pd.Timestamp(x))[:16]
    except (ValueError, TypeError):
        return None


def _cut(s):
    s = _nn(s)
    if not s:
        return ""
    s = " ".join(str(s).split())
    return s if len(s) <= DETAIL_CHARS else s[:DETAIL_CHARS - 1] + "…"


def _true(x):
    x = _nn(x)
    return x is not None and str(x).lower() in ("1", "true", "yes")


def _events():
    path = db.ROOT / "data/event_stream_2026-10-01.jsonl"
    if not path.exists():
        return []
    seen, out = set(), []
    for line in path.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            if e["event_id"] not in seen:  # the stream contains duplicates
                seen.add(e["event_id"])
                out.append(e)
    return out


def _rows(df, cid):
    return df[df.customer_id == cid].itertuples()


def timeline(engine, cid):
    X = engine.X
    if cid not in set(X["customer_master"].customer_id):
        raise KeyError(cid)
    offers = dict(zip(X["product_catalog"].product_id, X["product_catalog"].product_name))
    camp = {r.campaign_id: r for r in X["newsletter_campaigns"].itertuples()}
    out = []

    def add(at, src, title, detail="", flag=""):
        at = _ts(at)
        if at:
            out.append({"at": at, "source": src, "title": title, "detail": detail, "flag": flag,
                        "upcoming": pd.Timestamp(at) > SNAPSHOT and src != "live"})

    for r in _rows(X["customer_master"], cid):
        add(r.customer_since, "crm", "Became a MAINGAU customer")

    for r in _rows(X["energy_contracts"], cid):
        add(r.start_date, "contract", f"{r.tariff} ({r.commodity}) started")
        if _nn(r.cancellation_received_at):
            add(r.cancellation_received_at, "contract", f"Cancellation received: {r.tariff}", "", "bad")
        if _nn(r.meter_deregistered_at):
            add(r.meter_deregistered_at, "contract", "Gas meter deregistered", "", "bad")
        if _nn(r.price_guarantee_until):
            ends = pd.Timestamp(r.price_guarantee_until) > SNAPSHOT
            add(r.price_guarantee_until, "contract", f"Price guarantee {'ends' if ends else 'ended'}: {r.tariff}", "", "warn")
    for r in _rows(X["mobile_contracts"], cid):
        add(r.start_date, "contract", f"Mobile {r.plan} started")
        if _nn(r.min_term_end):
            ends = pd.Timestamp(r.min_term_end) > SNAPSHOT
            add(r.min_term_end, "contract", f"Mobile minimum term {'ends' if ends else 'ended'}")
    for r in _rows(X["autostrom_contracts"], cid):
        car = f"{_nn(r.car_brand) or ''} {_nn(r.car_model) or ''}".strip()
        add(r.start_date, "contract", "Autostrom started", car)
        if _nn(r.cancelled_at):
            add(r.cancelled_at, "contract", "Autostrom cancelled", "", "bad")

    cs = X["charge_sessions"][X["charge_sessions"].customer_id == cid].copy()
    if len(cs):
        cs["t"] = pd.to_datetime(cs.started_at, errors="coerce")
        cs = cs.sort_values("t")
        shown = set()
        for r in cs.tail(LATEST["charge"]).itertuples():
            shown.add(r.session_id)
            add(r.started_at, "charge", f"{r.charge_type} charge, {round(float(_nn(r.energy_kwh) or 0), 1)} kWh",
                f"{_nn(r.location_city) or ''} · {r.session_status}", "bad" if r.session_status != "completed" else "")
        for r in cs[(cs.session_status != "completed") & ~cs.session_id.isin(shown)].tail(3).itertuples():
            add(r.started_at, "charge", f"{r.charge_type} charge {r.session_status}", _cut(r.failure_reason), "bad")
        add(cs.t.min(), "charge", f"Charging history: {len(cs)} sessions", f"{int((cs.session_status != 'completed').sum())} not completed")

    for r in _rows(X["hems_devices"], cid):
        add(r.activated_at, "hems", f"{str(r.device_type).replace('_', ' ').capitalize()} connected", _nn(r.manufacturer) or "")
        if str(r.connection_status) != "online" and _nn(r.last_seen_at):
            add(r.last_seen_at, "hems", f"{str(r.device_type).replace('_', ' ').capitalize()} last seen", str(r.connection_status), "bad")

    for r in _rows(X["shop_orders"], cid):
        add(r.order_created_at, "shop", f"Ordered {r.product_name}",
            f"€{float(_nn(r.line_value_eur) or 0):,.0f} · {r.order_channel} · {r.order_status}",
            "bad" if r.order_status in ("cancelled", "returned") else "")

    for r in _rows(X["newsletter_performance"], cid):
        c = camp.get(r.campaign_id)
        subject = c.subject_line if c is not None else r.campaign_id
        if _nn(r.clicked_at):
            add(r.clicked_at, "nl", f"Clicked newsletter: {subject}", _cut(r.click_target), "good")
        elif _nn(r.opened_at):
            add(r.opened_at, "nl", f"Opened newsletter: {subject}",
                "machine open (Apple MPP), not a real read" if str(_nn(r.open_client_class) or "").startswith("apple_mpp") else "")
        if _true(r.unsubscribed):
            add(_nn(r.opened_at) or (c.sent_at if c is not None else None), "nl", "Unsubscribed from newsletter", "", "bad")

    ps = X["portal_sessions"][X["portal_sessions"].customer_id == cid].copy()
    if len(ps):
        ps["t"] = pd.to_datetime(ps.session_start, errors="coerce")
        for r in ps.sort_values("t").tail(LATEST["portal"]).itertuples():
            pages = str(_nn(r.pages_viewed) or "").replace("|", ", ")
            add(r.session_start, "portal", f"Portal visit ({r.client})", f"{pages} · {round(float(_nn(r.duration_s) or 0) / 60)} min")

    for r in _rows(X["service_interactions"], cid):
        csat = f" · CSAT {int(float(r.csat_1to5))}" if _nn(r.csat_1to5) is not None else ""
        add(r.created_at, "svc", f"Ticket: {str(r.category).replace('_', ' ')} via {str(r.channel).replace('_', ' ')}{csat}",
            _cut(_nn(r.message_text) or _nn(r.call_note)), "bad" if r.status != "closed" else "")
    for r in _rows(X["call_transcripts"], cid):
        add(r.call_started_at, "call", f"Call, {round(float(_nn(r.duration_s) or 0) / 60)} min", _cut(r.transcript))
    for r in _rows(X["service_nba_feedback"], cid):
        reaction = f" · {str(r.customer_reaction).replace('_', ' ')}" if _nn(r.customer_reaction) else ""
        add(r.shown_at, "agent", f"Agent suggestion: {offers.get(r.suggested_offer_id, r.suggested_offer_id)}",
            f"{str(r.agent_action).replace('_', ' ')}{reaction}", "good" if _true(r.converted_within_14d) else "")

    for r in _rows(X["nba_action_history"], cid):
        converted = _true(r.converted_within_14d)
        unchecked = "" if _true(r.consent_checked) else " · consent not checked"
        add(r.decided_at, "nba", f"Campaign: {offers.get(r.offer_id, r.offer_id)}",
            f"{str(r.channel).replace('_', ' ')} · {r.response}{' · converted' if converted else ''}{unchecked}",
            "good" if converted else ("" if r.response in ("clicked", "viewed", "held_out") else "muted"))

    for r in _rows(X["consent_status"], cid):
        add(r.updated_at, "consent", f"Consent {str(r.consent_type).replace('_', ' ')}: {r.status}", _cut(r.source),
            "bad" if r.status == "withdrawn" else "")

    for e in _events():
        if e.get("customer_id") != cid:
            continue
        pl = e.get("payload") or {}
        detail = " · ".join(f"{k.replace('_', ' ')}: {v}" for k, v in pl.items() if not isinstance(v, (dict, list)))
        add(e["occurred_at"], "live", e["event_type"].replace("_", " ").capitalize(), _cut(detail),
            "bad" if e["event_type"] in BAD_EVENTS else "")

    out.sort(key=lambda t: t["at"], reverse=True)
    counts = defaultdict(int)
    for t in out:
        counts[t["source"]] += 1
    first = min((t["at"] for t in out if t["source"] == "crm"), default=None)
    return {"customer_id": cid, "since": first, "snapshot": str(SNAPSHOT)[:16], "entries": out,
            "sources": [{"key": k, "label": v, "count": counts[k]} for k, v in SOURCES.items() if counts[k]]}
