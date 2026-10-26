import datetime as dt

SNAPSHOT = dt.datetime(2026, 9, 30, 23, 59)

DECISION_DAY = dt.datetime(2026, 10, 1)

SETTINGS = {
    "contact_cap_30d": 3,          # max marketing contacts per customer in 30 days
    "min_dclv_eur": 0.0,           # drop actions below this expected gain
    "exclude_dunning_from_level": 1,
}

SIGNAL_LIFT = {"strong": 2.0, "medium": 1.3, "weak": 1.0}

INTENT_LIFT = 1.5

CHANNELS = {
    # channel: (consent needed, contact cost key, label)
    "portal_popup":   ("portal_app_personalisation", "contact_cost_popup_eur", "Portal pop-up"),
    "app_push":       ("portal_app_personalisation", "contact_cost_popup_eur", "App push"),
    "newsletter_email": ("newsletter_email", "contact_cost_email_eur", "Newsletter e-mail"),
    "email":          ("marketing_email", "contact_cost_email_eur", "Marketing e-mail"),
    "sms":            ("marketing_sms", "contact_cost_sms_eur", "SMS"),
    "outbound_call":  ("marketing_phone", "contact_cost_call_eur", "Outbound call"),
}

BEHAVIOURAL = "behavioural"

CONTRACT = "contract"

INFORMAL = [r"\bhi\b", r"\bhallo\b", r"\bhey\b", r"\bdu\b", r"\bdir\b", r"\bdich\b", r"\bdein\w*", r"\beuch\b", r"\bihr\b(?! \w+ (?:Sie|Ihnen))",
            r"\bkönnt\b", r"\bhabt\b", r"\bseid\b", r"danke dir", r"tschüss", r"\blg\b", r"\bviele grüße\b", r"\bnervig\b", r"\bsuper\b"]

FORMAL = [r"sehr geehrte", r"guten tag", r"\bsie\b", r"\bihnen\b", r"\bihr(?:e|en|em|er)?\b(?=.*\bsie\b)", r"mit freundlichen grüßen",
          r"auf wiederhören", r"\bbitte teilen sie\b", r"vielen dank"]

DRIVER_LABEL = {"open_complaint": "open complaint", "tickets_12m_ge2": "2+ tickets in 12 months", "csat_le2": "low satisfaction rating",
                "dunning_ge2": "dunning level 2+", "failed_charges_30d_ge3": "3+ failed charging sessions", "price_guarantee_ends_90d": "price guarantee ending"}

SERVICE_DRIVERS = [("open complaint", "open_complaint"), ("tickets in 12m", "tickets_12m_ge2"), ("low CSAT", "csat_le2"),
                   ("dunning level", "dunning_ge2"), ("failed charges", "failed_charges_30d_ge3")]
