"""Builds the web app: slims engine_output.json and inlines it into app.html -> out/nba_console.html"""
import json
from pathlib import Path
from templates import TEMPLATES
import build_360

ROOT = Path(__file__).parent
d = json.load(open(ROOT / "out" / "engine_output.json", encoding="utf-8"))


def slim_c(c):
    return {
        "id": c["customer_id"], "city": c["city"], "since": c["customer_since"], "by": c["birth_year"], "hh": c["household_size"],
        "portal": c["portal_account"], "app": c["app_installed"], "lang": c["language"], "consent": c["consent"],
        "clv": c["clv_now"], "churn": c["churn_now"], "parts": c["churn_parts"],
        "margin": c["value"]["annual_margin"], "cts": c["value"]["cost_to_serve"], "svcImpact": c["value"]["clv_service_impact"],
        "drivers": c["value"]["churn_drivers"], "lines": c["value"]["lines"],
        "products": c["products"],
        "signals": {k: [v["value"], v["class"], v["evidence"][:2]] for k, v in c["signals"].items() if k != "shop_customer"},
        "open": [{"cat": t.get("category"), "at": str(t.get("created_at"))[:16], "ch": t.get("channel"), "txt": (t.get("text") or "")[:220]} for t in c["open_tickets"]],
        "tickets": [{"cat": t["category"], "at": t["created_at"], "ch": t["channel"], "st": t["status"], "csat": t["csat"], "res": t["resolution"],
                     "txt": (t["text"] or "")[:220], "rep": t["repeat"]} for t in c["recent_tickets"][:4]],
        "tone": c["tone"], "toneWhy": c["tone_reason"], "toneSample": c["tone_sample"],
        "contacts": c["contacts_30d"], "portal90": c["portal_sessions_90d"], "mail": c["email_engagement"],
        "legacy": c["legacy_actions"][:4], "case": c["service_case"], "prof": c["profiling"],
        "chans": [{"ch": x["channel"], "ok": x["allowed"], "no": x["why_not"]} for x in c["channels"]],
        "cands": [{"o": r["offer"], "n": r["name"], "t": r["type"], "s": r["strength"], "why": r["why"], "pb": r["p_base"], "lift": r["lift_note"],
                   "acc": r["clv_accept"], "rej": r["clv_reject"], "blk": r["blocked"], "d": r["dclv"], "ch": r["channel"], "p": r["p"],
                   "pc": [[x["channel"], x["p"], x["dclv"]] for x in r["per_channel"]]} for r in c["candidates"]],
        "cancel": c["cancellation_pending"],
        "guar": (c["signals"].get("guarantee_ending") or {}).get("value"),
        "py": {"a": c["decision"]["action"], "o": (c["decision"].get("pick") or {}).get("offer"), "ch": (c["decision"].get("pick") or {}).get("channel")},
    }


web = {
    "snapshot": d["snapshot"], "settings": d["settings"], "fcr": d["fcr_rate"], "params": d["params"],
    "signalLift": d["signal_lift"], "intentLift": d["intent_lift"], "acc": d["acceptance"], "catalog": d["catalog"],
    "legacy": d["legacy"], "replay": d["replay"], "dups": d["replay_duplicates"], "selfCheck": d["self_check_violations"],
    "templates": TEMPLATES, "customers": [slim_c(c) for c in d["customers"]],
}
web["x360"], web["sources"] = build_360.build()
blob = json.dumps(web, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = (ROOT / "app.html").read_text(encoding="utf-8").replace("/*__DATA__*/null", blob)
(ROOT / "out" / "nba_console.html").write_text(html, encoding="utf-8")
print("data KB", len(blob) // 1024, "| page KB", len(html.encode()) // 1024)
