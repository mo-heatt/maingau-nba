from .constants import SETTINGS
from .signals import has


def arbitrate(s, sc, settings=SETTINGS):
    """Pick the action. Same logic is mirrored in the web app so marketing can change the settings."""
    log = []
    if has(s, "cancellation_pending"):
        return {"action": "human_review", "title": "Hand to retention team", "reason": "Cancellation received – a person decides, no automated contact.", "log": ["Rule: cancellation pending → human review"]}
    svc = next((r for r in sc["candidates"] if r["offer"] == "P-SV-01"), None)
    open_sales = [r for r in sc["candidates"] if r["offer"] != "P-SV-01" and not r["blocked"]]
    if sc["service_case"]:
        log.append("Rule: " + ", ".join(sc["service_case"]) + " → sales content blocked")
    weights={"low":0.5,"normal":1.0,"high":1.5}
    viable = sorted([r for r in open_sales if r["dclv"] > settings["min_dclv_eur"]], key=lambda r:r["dclv"]*weights[settings.get("priorities",{}).get(r["offer"],"normal")], reverse=True)
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
