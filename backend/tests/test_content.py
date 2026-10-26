"""Du/Sie detection and the approved message templates."""
from app.engine.content import customer_lines, message, tone_from_texts
from app.engine.templates import TEMPLATES


def test_informal_words_win():
    tone, _, inf, frm = tone_from_texts(["Hey, kannst du mir bitte helfen? Danke dir!"])
    assert tone == "du"
    assert inf > frm


def test_formal_words_win():
    tone, _, inf, frm = tone_from_texts(["Sehr geehrte Damen und Herren, vielen Dank für Ihre Antwort."])
    assert tone == "sie"
    assert frm > inf


def test_tie_defaults_to_formal():
    tone, *_ = tone_from_texts(["Hey, guten Tag!"])  # 1 informal vs 1 formal
    assert tone == "sie"


def test_no_own_words_defaults_to_formal():
    tone, why, *_ = tone_from_texts(["..."])
    assert tone == "sie"
    assert "default" in why


def test_customer_lines_extracts_only_the_customers_own_words():
    transcript = "Agent: Guten Tag\nKunde: Hallo, ich habe ein Problem\nAgent: Wie kann ich helfen?\nKUNDE: Es geht um meine Rechnung"
    assert customer_lines(transcript) == [" Hallo, ich habe ein Problem", " Es geht um meine Rechnung"]


def test_guarantee_ending_in_the_future():
    s = {"tone": "du", "signals": {"guarantee_ending": {"value": "2026-11-15"}}}
    m = message(s, {"pick": {"offer": "P-EN-02"}})
    assert "am 15.11.2026 aus" in m["body"]
    assert "{" not in m["body"]  # placeholder fully replaced
    assert m["subject"] == TEMPLATES["P-EN-02"]["du"][0]
    assert m["tone"] == "du"


def test_guarantee_already_ended():
    s = {"tone": "sie", "signals": {"guarantee_ending": {"value": "2026-09-15"}}}
    m = message(s, {"pick": {"offer": "P-EN-02"}})
    assert "seit dem 15.09.2026 nicht mehr" in m["body"]


def test_missing_date_falls_back_to_bald():
    m = message({"tone": "du", "signals": {}}, {"pick": {"offer": "P-EN-02"}})
    assert "bald aus" in m["body"]


def test_no_pick_means_no_message():
    assert message({"tone": "du", "signals": {}}, {"pick": None}) is None


def test_tones_differ_for_the_same_offer():
    du = message({"tone": "du", "signals": {}}, {"pick": {"offer": "P-MO-01"}})
    sie = message({"tone": "sie", "signals": {}}, {"pick": {"offer": "P-MO-01"}})
    assert du["body"] != sie["body"]
    assert "Hallo!" in du["body"] and "Guten Tag" in sie["body"]


def test_every_offer_has_both_approved_tones():
    for oid, templates in TEMPLATES.items():
        assert set(templates) == {"du", "sie"}, oid
        for tone, (subject, body) in templates.items():
            assert subject and body, f"{oid}/{tone}"
            assert "{name}" not in body, "mock data has no names"
