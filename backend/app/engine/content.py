import re
import datetime as dt
from .constants import INFORMAL, FORMAL, DECISION_DAY
from .templates import TEMPLATES


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


def message(s, decision):
    pick = decision.get("pick")
    if not pick:
        return None
    t = s["tone"]
    if str(s.get('language','de')).lower().startswith('en'):
        if pick.get('type')=='service':
            return {'language':'en','tone':t,'subject':'Help with your service issue','body':'Hello, we would like to help clarify your open service issue. Please tell us what happened and whether now is a convenient time to talk.'}
        return {'language':'en','tone':t,'subject':'A suitable next step from MAINGAU','body':'Hello, '+pick['name']+' may be a suitable option to review. Please check the applicable terms, availability and suitability before deciding.'}
    subj, body = TEMPLATES[pick["offer"]][t]
    g = s["signals"].get("guarantee_ending", {}).get("value")
    if g:
        d = dt.datetime.strptime(g, "%Y-%m-%d")
        gt = (f"am {d:%d.%m.%Y} aus" if d >= DECISION_DAY else f"seit dem {d:%d.%m.%Y} nicht mehr")
    else:
        gt = "bald aus"
    return {"tone": t, "subject": subj, "body": body.replace("{guarantee_text}", gt)}
