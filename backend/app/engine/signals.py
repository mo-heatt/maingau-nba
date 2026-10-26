from .constants import BEHAVIOURAL, SETTINGS


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


def service_case(s):
    """Reasons that make this an open service case (blocks sales)."""
    r = []
    if has(s, "open_complaint"): r.append("open complaint")
    dl = s["signals"].get("dunning_level", {"value": 0})["value"]
    if dl >= SETTINGS["exclude_dunning_from_level"]: r.append(f"dunning level {dl}")
    if has(s, "cancellation_pending"): r.append("cancellation received")
    return r
