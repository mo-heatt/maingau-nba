"""Step 5b: tone (Du/Sie) from the customer's own words, and German message templates.

Templates are the "approved templates" from the brief. In this MVP the text is
filled by rules; an LLM can later rewrite inside these templates (deep dive C).
"""
import re

DU = [r"\bhi\b", r"\bhallo\b", r"\bhey\b", r"\bdir\b", r"\bdich\b", r"\bdu\b", r"\beuch\b", r"\bihr\b",
      r"\bkönnt\b", r"\bhabt\b", r"\bseid\b", r"\btschüss\b", r"\bdanke dir\b", r"\bnervig\b", r"\bliebe grüße\b", r"\blg\b"]
SIE = [r"sehr geehrte", r"\bguten tag\b", r"mit freundlichen grüßen", r"\bihnen\b", r"\bsie\b",
       r"\bihr(e|en|em|er)?\b(?= (vertrag|angebot|rechnung|kundenkonto))", r"auf wiederhören", r"\bbitte teilen sie\b"]


def detect_tone(texts):
    """Return (tone, evidence). Default 'sie' (safe, formal) when there is no signal."""
    du = sie = 0
    for t in texts:
        low = t.lower()
        du += sum(len(re.findall(p, low)) for p in DU)
        sie += sum(len(re.findall(p, low)) for p in SIE)
    if du == 0 and sie == 0:
        return "sie", "no own messages: formal default"
    if du > sie:
        return "du", f"writes informally ({du} Du-signals vs {sie} Sie-signals)"
    return "sie", f"writes formally ({sie} Sie-signals vs {du} Du-signals)"


# (subject, body) per offer and tone. Short, no fake urgency, no personal prices.
T = {
    "P-EN-01": {
        "sie": ("Strom von MAINGAU – passend zu Ihrem Autostrom",
                "Sie laden bereits mit MAINGAU Autostrom. Mit StromAktiv beziehen Sie auch Ihren Haushaltsstrom von uns – flexibel und ohne lange Bindung."),
        "du": ("Strom von MAINGAU – passend zu deinem Autostrom",
               "Du lädst schon mit MAINGAU Autostrom. Mit StromAktiv bekommst du auch deinen Haushaltsstrom von uns – flexibel und ohne lange Bindung."),
    },
    "P-EN-02": {
        "sie": ("Ihre Preisgarantie läuft aus – sichern Sie sich die nächste",
                "Ihre Preisgarantie endet bald. Mit StromGarant erhalten Sie erneut 24 Monate Preissicherheit. Wir beraten Sie gerne persönlich."),
        "du": ("Deine Preisgarantie läuft aus – sichere dir die nächste",
               "Deine Preisgarantie endet bald. Mit StromGarant hast du wieder 24 Monate Preissicherheit. Wir beraten dich gerne."),
    },
    "P-EN-03": {
        "sie": ("Ein eigener Tarif für Ihre Wärmepumpe",
                "Für Wärmepumpen gibt es bei uns StromWärme – einen Tarif speziell für Heizstrom. Gerne prüfen wir, ob er für Ihren Haushalt passt."),
        "du": ("Ein eigener Tarif für deine Wärmepumpe",
               "Für Wärmepumpen gibt es bei uns StromWärme – einen Tarif speziell für Heizstrom. Wir prüfen gerne, ob er für dich passt."),
    },
    "P-EN-04": {
        "sie": ("Gas und Strom aus einer Hand", "Mit GasAktiv beziehen Sie auch Ihr Gas von MAINGAU – flexibel und ohne lange Bindung."),
        "du": ("Gas und Strom aus einer Hand", "Mit GasAktiv bekommst du auch dein Gas von MAINGAU – flexibel und ohne lange Bindung."),
    },
    "P-EN-05": {
        "sie": ("Strom dann nutzen, wenn er günstig ist",
                "Mit Ihrem Smart Meter können Sie unseren dynamischen Stromtarif nutzen und Verbrauch in günstige Stunden verlegen."),
        "du": ("Strom dann nutzen, wenn er günstig ist",
               "Mit deinem Smart Meter kannst du unseren dynamischen Stromtarif nutzen und deinen Verbrauch in günstige Stunden legen."),
    },
    "P-MO-01": {
        "sie": ("Mobilfunk von MAINGAU", "Als Energiekundin oder -kunde können Sie auch Ihren Mobilfunk bei uns haben – Tarife von 10 bis 100 GB."),
        "du": ("Mobilfunk von MAINGAU", "Du bist schon Energiekunde bei uns – Mobilfunk gibt es auch: Tarife von 10 bis 100 GB."),
    },
    "P-MO-02": {
        "sie": ("Mehr Datenvolumen für Sie", "Sie haben Ihr Datenvolumen zuletzt öfter ausgeschöpft. Mit dem Upgrade auf die nächste Stufe surfen Sie entspannter."),
        "du": ("Mehr Datenvolumen für dich", "Dein Datenvolumen war zuletzt öfter aufgebraucht. Mit dem Upgrade auf die nächste Stufe surfst du entspannter."),
    },
    "P-MO-03": {
        "sie": ("Eine Zusatz-SIM für Ihren Haushalt", "Mit einer Zusatz-SIM können weitere Personen in Ihrem Haushalt Ihren Tarif mitnutzen."),
        "du": ("Eine Zusatz-SIM für deinen Haushalt", "Mit einer Zusatz-SIM können weitere Personen in deinem Haushalt deinen Tarif mitnutzen."),
    },
    "P-IN-01": {
        "sie": ("Internet von MAINGAU", "Neben Energie bieten wir auch Internet per DSL oder Glasfaser an. Gerne prüfen wir die Verfügbarkeit an Ihrer Adresse."),
        "du": ("Internet von MAINGAU", "Neben Energie gibt es bei uns auch Internet per DSL oder Glasfaser. Wir prüfen gerne die Verfügbarkeit bei dir."),
    },
    "P-SL-01": {
        "sie": ("Ihre Energie im Haus intelligent steuern",
                "Mit dem HEMS Starter-Set steuern Sie PV-Anlage, Wärmepumpe oder Wallbox in einer App und nutzen mehr eigenen Strom."),
        "du": ("Deine Energie im Haus clever steuern",
               "Mit dem HEMS Starter-Set steuerst du PV-Anlage, Wärmepumpe oder Wallbox in einer App und nutzt mehr eigenen Strom."),
    },
    "P-SL-02": {
        "sie": ("Mehr aus Ihrem Speicher holen", "Die Speicher-Optimierung lädt Ihren Batteriespeicher dann, wenn es sich am meisten lohnt."),
        "du": ("Mehr aus deinem Speicher holen", "Die Speicher-Optimierung lädt deinen Batteriespeicher dann, wenn es sich am meisten lohnt."),
    },
    "P-SL-03": {
        "sie": ("Ihr Auto mit Ihrem eigenen Strom laden", "Mit der Wallbox-Integration lädt Ihr Auto bevorzugt mit Solarstrom vom eigenen Dach."),
        "du": ("Dein Auto mit deinem eigenen Strom laden", "Mit der Wallbox-Integration lädt dein Auto bevorzugt mit Solarstrom vom eigenen Dach."),
    },
    "P-SH-01": {
        "sie": ("Strom vom eigenen Balkon", "Mit dem Balkonkraftwerk 800 W erzeugen Sie einen Teil Ihres Stroms selbst."),
        "du": ("Strom vom eigenen Balkon", "Mit dem Balkonkraftwerk 800 W erzeugst du einen Teil deines Stroms selbst."),
    },
    "P-SH-02": {
        "sie": ("Zuhause laden mit der eigenen Wallbox", "Mit der Wallbox 11 kW laden Sie Ihr E-Auto bequem und sicher zu Hause."),
        "du": ("Zuhause laden mit der eigenen Wallbox", "Mit der Wallbox 11 kW lädst du dein E-Auto bequem und sicher zu Hause."),
    },
    "P-SH-03": {
        "sie": ("Heizkosten im Griff mit smarten Thermostaten", "Smarte Thermostate regeln Ihre Heizung nach Zeitplan und helfen, Gas zu sparen."),
        "du": ("Heizkosten im Griff mit smarten Thermostaten", "Smarte Thermostate regeln deine Heizung nach Zeitplan und helfen dir, Gas zu sparen."),
    },
    "P-SH-04": {
        "sie": ("Stromfresser finden mit Smart Plugs", "Mit dem Smart Plug 4er-Set sehen Sie, welche Geräte wie viel Strom verbrauchen."),
        "du": ("Stromfresser finden mit Smart Plugs", "Mit dem Smart Plug 4er-Set siehst du, welche Geräte wie viel Strom verbrauchen."),
    },
    "P-AS-01": {
        "sie": ("Unterwegs laden mit MAINGAU Autostrom", "Mit MAINGAU Autostrom laden Sie Ihr E-Auto an über 900.000 Ladepunkten in Europa – per Karte oder App."),
        "du": ("Unterwegs laden mit MAINGAU Autostrom", "Mit MAINGAU Autostrom lädst du dein E-Auto an über 900.000 Ladepunkten in Europa – per Karte oder App."),
    },
    "P-SV-01": {
        "sie": ("Rückruf durch den Kundenservice",
                "Gesprächsleitfaden: Anliegen aufnehmen, Lösung zusagen, Mahnverfahren bis zur Klärung pausieren. Kein Verkaufsangebot."),
        "du": ("Rückruf durch den Kundenservice",
               "Gesprächsleitfaden: Anliegen aufnehmen, Lösung zusagen, Mahnverfahren bis zur Klärung pausieren. Kein Verkaufsangebot. Kunde duzt – locker bleiben."),
    },
}


def message(offer_id, tone):
    subject, body = T[offer_id][tone]
    return {"subject": subject, "body": body}
