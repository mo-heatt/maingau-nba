"""Case Radar: finds service-first customers who are stuck, so a person steps in before it escalates.

Rules, adapted from our Case Radar prototype to the fields Maingau's data has. A customer is
flagged when a complaint is still open and at least one of these is true:
  1. Money demanded during an open complaint: the bill is in dunning (level 1 or higher).
  2. Came back unsolved: a contact was not solved the first time and the customer wrote or
     called again within 30 days.
The flag is a rule, not AI, so every flag can be explained in one line.
"""
import json

import pandas as pd

from . import database as db

AS_OF = pd.Timestamp("2026-10-01")
LOOKBACK_DAYS = 90
REPEAT_WITHIN_DAYS = 30
CHANNEL = {"email": "email", "phone": "phone", "portal_form": "web form", "chat": "chat"}
OFFER = {"P-EN-02": "StromGarant", "P-AS-01": "MAINGAU Autostrom", "P-EN-05": "dynamic tariff", "P-SH-01": "Balkonkraftwerk"}


def _events():
    path = db.ROOT / "data/event_stream_2026-10-01.jsonl"
    if not path.exists():
        return []
    seen, out = set(), []
    for line in path.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            if e["event_id"] not in seen:  # the stream has duplicates
                seen.add(e["event_id"])
                out.append(e)
    return out


def _day(ts):
    return pd.Timestamp(ts).strftime("%d.%m.")


def radar(engine):
    X = engine.X
    si = X["service_interactions"].copy()
    si["c"] = pd.to_datetime(si.created_at)
    si = si.sort_values("c")
    dunning = X["energy_contracts"].groupby("customer_id").dunning_level.max()
    city = X["customer_master"].set_index("customer_id").city
    hist = X["nba_action_history"]
    events = _events()

    open_complaints = si[(si.status == "open") & (si.category == "complaint")]
    cards = []
    for cid, g in si[si.customer_id.isin(open_complaints.customer_id)].groupby("customer_id"):
        recent = g[g.c >= AS_OF - pd.Timedelta(days=LOOKBACK_DAYS)].reset_index(drop=True)
        why, start = [], None
        level = int(dunning.get(cid, 0) or 0)
        for e in events:  # the stream can raise the level after the snapshot
            if e["customer_id"] == cid and e["event_type"] == "dunning_level_changed":
                level = max(level, int(e["payload"]["new_level"]))
        for i in range(1, len(recent)):
            prev, cur = recent.loc[i - 1], recent.loc[i]
            if not bool(prev.first_contact_resolution) and (cur.c - prev.c).days <= REPEAT_WITHIN_DAYS:
                why.append(f"Came back unsolved: contact on {_day(prev.c)} not solved, contacted again on {_day(cur.c)}")
                start = prev.c if start is None else start
                break
        opened = open_complaints[open_complaints.customer_id == cid].c.min()
        if level >= 1:
            why.append(f"Payment reminders running (dunning level {level}) while the complaint from {_day(opened)} is open")
        if not why:
            continue
        start = min(start or opened, opened)

        timeline = [{
            "at": str(r.c), "kind": "contact", "label": f"{CHANNEL.get(r.channel, r.channel)} · {r.category}",
            "text": (r.message_text if isinstance(r.message_text, str) else r.call_note if isinstance(r.call_note, str) else ""),
            "solved": r.status == "closed" and bool(r.first_contact_resolution),
            "status": "open" if r.status == "open" else ("solved" if bool(r.first_contact_resolution) else "closed, not solved"),
        } for r in recent.itertuples()]
        sales = hist[(hist.customer_id == cid) & (hist.delivery_status == "delivered") & (pd.to_datetime(hist.decided_at) >= start)]
        for r in sales.itertuples():
            timeline.append({"at": str(r.decided_at), "kind": "sale", "label": f"Sales message: {OFFER.get(r.offer_id, r.offer_id)} by {r.channel.replace('_', ' ')}",
                             "text": "", "solved": False, "status": r.response})
        for e in events:
            if e["customer_id"] != cid:
                continue
            if e["event_type"] == "dunning_level_changed":
                p = e["payload"]
                timeline.append({"at": e["occurred_at"], "kind": "billing", "label": f"Dunning level {p['old_level']} → {p['new_level']}", "text": "", "solved": False, "status": "money demanded"})
            elif e["event_type"] in ("ticket_updated", "ticket_created"):
                note = e["payload"].get("note") or e["payload"].get("text") or e["payload"].get("message_text") or e["event_type"].replace("_", " ")
                timeline.append({"at": e["occurred_at"], "kind": "contact", "label": "ticket update", "text": str(note), "solved": False, "status": "open"})
        timeline.sort(key=lambda t: t["at"])

        texts = [m for m in recent.message_text if isinstance(m, str) and m.strip()]  # the customer's own words
        actions = [{"id": "assign_person", "label": "Assign to a person", "done": "Assigned to you"}]
        if level >= 1:
            actions.insert(0, {"id": "pause_reminders", "label": "Pause payment reminders", "done": "Payment reminders paused"})
        cards.append({
            "customer_id": cid, "city": city.get(cid, ""), "waiting_since": str(start.date()),
            "days_waiting": int((AS_OF - start).days), "contacts": len(recent), "dunning_level": level,
            "sales_while_waiting": int(len(sales)), "why": why, "quote": texts[-1] if texts else "",
            "timeline": timeline, "actions": actions,
        })
    cards.sort(key=lambda c: (-len(c["why"]), -c["dunning_level"], -c["days_waiting"]))
    return {"as_of": str(AS_OF.date()), "open_complaints": int(open_complaints.customer_id.nunique()), "cards": cards,
            "rules": ["Money demanded during an open complaint (dunning level 1 or higher)",
                      f"Came back unsolved: not solved the first time, contacted again within {REPEAT_WITHIN_DAYS} days"]}
