"""Approved German message templates per offer and tone (Du / Sie).

Rules for every template: no personalised prices, no fake urgency, no pressure.
{name} is never used: the mock data has no names. Placeholders are filled by the engine.
"""

TEMPLATES = {
    "P-EN-01": {
        "sie": ("Strom von MAINGAU – einfach und flexibel",
                "Guten Tag, Sie beziehen bereits Leistungen von MAINGAU. Mit StromAktiv können Sie auch Ihren Strom bei uns beziehen – flexibel und ohne lange Bindung. Die Details finden Sie in Ihrem Kundenportal."),
        "du": ("Dein Strom von MAINGAU",
               "Hallo! Du bist schon Kunde bei MAINGAU. Mit StromAktiv kannst du auch deinen Strom bei uns beziehen – flexibel und ohne lange Bindung. Alle Details findest du in deinem Kundenportal."),
    },
    "P-EN-02": {
        "sie": ("Ihre Preisgarantie: jetzt verlängern",
                "Guten Tag, Ihre Preisgarantie läuft {guarantee_text}. Mit StromGarant sichern Sie sich erneut 24 Monate Preissicherheit. Gern erläutern wir Ihnen die Konditionen – Sie entscheiden in Ruhe."),
        "du": ("Deine Preisgarantie verlängern",
               "Hallo! Deine Preisgarantie läuft {guarantee_text}. Mit StromGarant hast du wieder 24 Monate Preissicherheit. Schau dir die Konditionen in Ruhe an."),
    },
    "P-EN-03": {
        "sie": ("Der passende Tarif für Ihre Wärmepumpe",
                "Guten Tag, wenn Sie inzwischen mit einer Wärmepumpe heizen, ist StromWärme der passende Tarif: speziell für Wärmepumpenstrom kalkuliert. Gern prüfen wir, ob der Wechsel für Sie sinnvoll ist."),
        "du": ("Der Tarif für deine Wärmepumpe",
               "Hallo! Heizt du inzwischen mit einer Wärmepumpe? Dann passt StromWärme – speziell für Wärmepumpenstrom. Wir prüfen gern mit dir, ob sich der Wechsel lohnt."),
    },
    "P-EN-05": {
        "sie": ("Dynamischer Stromtarif für Ihr Smart Home",
                "Guten Tag, mit Ihrem Smart Meter können Sie unseren dynamischen Stromtarif nutzen und Verbrauch in günstige Stunden verschieben. Informationen dazu finden Sie in Ihrem Kundenportal."),
        "du": ("Dein dynamischer Stromtarif",
               "Hallo! Mit deinem Smart Meter kannst du unseren dynamischen Tarif nutzen und Strom dann verbrauchen, wenn er günstig ist. Infos findest du im Kundenportal."),
    },
    "P-MO-01": {
        "sie": ("Mobilfunk von MAINGAU",
                "Guten Tag, neben Energie bietet MAINGAU auch Mobilfunktarife mit 10, 30 oder 100 GB. Wenn Sie möchten, finden Sie alle Tarife im Kundenportal."),
        "du": ("Mobilfunk von MAINGAU",
               "Hallo! MAINGAU hat auch Handytarife mit 10, 30 oder 100 GB. Wenn du magst, schau sie dir im Kundenportal an."),
    },
    "P-MO-02": {
        "sie": ("Mehr Datenvolumen für Sie",
                "Guten Tag, Ihr Datenvolumen war in den letzten Monaten mehrfach aufgebraucht. Mit dem Upgrade auf die nächste Stufe surfen Sie ohne Drosselung weiter. Sie können jederzeit im Portal wechseln."),
        "du": ("Mehr Datenvolumen für dich",
               "Hallo! Dein Datenvolumen war zuletzt öfter aufgebraucht. Mit dem Upgrade auf die nächste Stufe surfst du ohne Drosselung weiter. Wechseln kannst du jederzeit im Portal."),
    },
    "P-MO-03": {
        "sie": ("Zusatz-SIM für Ihren Haushalt",
                "Guten Tag, mit einer Zusatz-SIM nutzen weitere Personen in Ihrem Haushalt Ihren MAINGAU-Tarif. Details finden Sie im Kundenportal."),
        "du": ("Zusatz-SIM für deinen Haushalt",
               "Hallo! Mit einer Zusatz-SIM können weitere Personen in deinem Haushalt deinen MAINGAU-Tarif nutzen. Details findest du im Kundenportal."),
    },
    "P-IN-01": {
        "sie": ("Internet von MAINGAU",
                "Guten Tag, MAINGAU bietet auch Internet per DSL und Glasfaser an. Ob Ihre Adresse versorgt wird, können Sie im Kundenportal prüfen."),
        "du": ("Internet von MAINGAU",
               "Hallo! MAINGAU hat auch Internet per DSL und Glasfaser. Ob deine Adresse versorgt wird, kannst du im Kundenportal prüfen."),
    },
    "P-SL-01": {
        "sie": ("Energie zu Hause intelligent steuern",
                "Guten Tag, mit dem HEMS Starter-Set steuern Sie PV-Anlage, Wärmepumpe oder Wallbox in einer App und nutzen Ihren eigenen Strom besser. Mehr dazu im Kundenportal."),
        "du": ("Deine Energie zu Hause smart steuern",
               "Hallo! Mit dem HEMS Starter-Set steuerst du PV, Wärmepumpe oder Wallbox in einer App und nutzt deinen eigenen Strom besser. Mehr dazu im Kundenportal."),
    },
    "P-SL-02": {
        "sie": ("Mehr aus Ihrem Speicher holen",
                "Guten Tag, die Speicher-Optimierung lädt und entlädt Ihren Heimspeicher automatisch zum passenden Zeitpunkt. Sie können sie in der App hinzubuchen."),
        "du": ("Mehr aus deinem Speicher holen",
               "Hallo! Die Speicher-Optimierung lädt und entlädt deinen Heimspeicher automatisch zur richtigen Zeit. Du kannst sie in der App hinzubuchen."),
    },
    "P-SL-03": {
        "sie": ("Ihr E-Auto mit eigenem Strom laden",
                "Guten Tag, mit der Wallbox-Integration lädt Ihr E-Auto bevorzugt, wenn Ihre PV-Anlage Strom liefert. Die Funktion können Sie in der App aktivieren."),
        "du": ("Dein E-Auto mit eigenem Strom laden",
               "Hallo! Mit der Wallbox-Integration lädt dein E-Auto bevorzugt, wenn deine PV-Anlage Strom liefert. Aktivieren kannst du das in der App."),
    },
    "P-SH-01": {
        "sie": ("Strom vom eigenen Balkon",
                "Guten Tag, mit einem Balkonkraftwerk erzeugen Sie einen Teil Ihres Stroms selbst. Informationen zu Montage und Anmeldung finden Sie in unserem Shop."),
        "du": ("Strom vom eigenen Balkon",
               "Hallo! Mit einem Balkonkraftwerk erzeugst du einen Teil deines Stroms selbst. Infos zu Montage und Anmeldung findest du in unserem Shop."),
    },
    "P-SH-02": {
        "sie": ("Zuhause laden mit der eigenen Wallbox",
                "Guten Tag, Sie laden Ihr E-Auto bisher unterwegs. Mit einer eigenen Wallbox laden Sie auch bequem zu Hause. Informationen finden Sie in unserem Shop."),
        "du": ("Zuhause laden mit deiner eigenen Wallbox",
               "Hallo! Du lädst dein E-Auto bisher unterwegs. Mit einer eigenen Wallbox lädst du auch bequem zu Hause. Infos findest du in unserem Shop."),
    },
    "P-SH-03": {
        "sie": ("Heizkosten mit smarten Thermostaten senken",
                "Guten Tag, smarte Thermostate regeln Ihre Heizung nach Zeitplan und helfen, Gas zu sparen. Mehr dazu finden Sie in unserem Shop."),
        "du": ("Heizkosten mit smarten Thermostaten senken",
               "Hallo! Smarte Thermostate regeln deine Heizung nach Zeitplan und helfen dir, Gas zu sparen. Mehr dazu in unserem Shop."),
    },
    "P-SH-04": {
        "sie": ("Verbrauch sichtbar machen",
                "Guten Tag, mit Smart Plugs sehen Sie, welche Geräte wie viel Strom verbrauchen. Mehr dazu in unserem Shop."),
        "du": ("Verbrauch sichtbar machen",
               "Hallo! Mit Smart Plugs siehst du, welche Geräte wie viel Strom verbrauchen. Mehr dazu in unserem Shop."),
    },
    "P-AS-01": {
        "sie": ("Unterwegs laden mit MAINGAU Autostrom",
                "Guten Tag, mit MAINGAU Autostrom laden Sie Ihr E-Auto an über 927.000 Ladepunkten in Europa – per Karte oder App, AC für 0,52 €/kWh. Alle Details auf unserer Website."),
        "du": ("Unterwegs laden mit MAINGAU Autostrom",
               "Hallo! Mit MAINGAU Autostrom lädst du dein E-Auto an über 927.000 Ladepunkten in Europa – per Karte oder App, AC für 0,52 €/kWh. Alle Details auf unserer Website."),
    },
    "P-SV-01": {
        "sie": ("Wir kümmern uns um Ihr Anliegen",
                "Guten Tag, es tut uns leid, dass Ihr Anliegen noch nicht gelöst ist. Ein Mitarbeiter aus unserem Kundenservice meldet sich persönlich bei Ihnen, um es zu klären."),
        "du": ("Wir kümmern uns um dein Anliegen",
               "Hallo! Es tut uns leid, dass dein Anliegen noch nicht gelöst ist. Jemand aus unserem Kundenservice meldet sich persönlich bei dir, um das zu klären."),
    },
}
