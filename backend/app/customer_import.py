"""Import one customer (master data + contact consents) next to the source data.

Rows are appended to source_records, which can't be updated or deleted afterwards (database triggers),
and every import is written to the audit log. A dry run validates and previews without storing anything.
"""
import datetime as dt
import json
import re
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from . import database as db

CONSENT_TYPES = ["newsletter_email", "marketing_email", "marketing_phone", "marketing_sms",
                 "portal_app_personalisation", "profiling_analytics"]
LEGAL_BASIS = {"portal_app_personalisation": "consent (§25 TDDDG) / portal terms",
               "profiling_analytics": "consent (§25 TDDDG) / portal terms"}
DEFAULT_BASIS = "consent (Art. 6(1)(a) GDPR, §7 UWG)"
Status = Literal["granted", "not_given", "withdrawn"]


class Master(BaseModel):
    customer_id: str = Field(pattern=r"^MG-\d{6}$", description="Format MG-123456")
    customer_type: Literal["B2C", "B2B"] = "B2C"
    customer_since: dt.date
    birth_year: Optional[int] = Field(default=None, ge=1900, le=2010)
    postal_code_prefix: str = Field(pattern=r"^\d{3}$", description="First three digits of the postcode")
    city: str = Field(min_length=1, max_length=80)
    household_size: int = Field(default=1, ge=1, le=12)
    portal_account: bool = False
    app_installed: bool = False
    preferred_contact_language: Literal["de", "en"] = "de"

    @field_validator("postal_code_prefix", mode="before")
    @classmethod
    def as_text(cls, v):
        return str(v).strip().zfill(3) if v is not None and str(v).strip() else v

    @field_validator("customer_since")
    @classmethod
    def not_in_future(cls, v):
        if v > dt.date.today():
            raise ValueError("customer_since can't be in the future")
        return v

    @field_validator("city")
    @classmethod
    def clean_city(cls, v):
        v = v.strip()
        if re.search(r"[<>{}]", v):
            raise ValueError("city contains characters that are not allowed")
        return v


class CustomerImport(BaseModel):
    customer: Master
    # Missing consent types are stored as not_given: no consent is ever assumed.
    consents: Dict[str, Status] = {}
    dry_run: bool = False

    @field_validator("consents")
    @classmethod
    def known_types(cls, v):
        unknown = sorted(set(v) - set(CONSENT_TYPES))
        if unknown:
            raise ValueError("unknown consent type: " + ", ".join(unknown) + ". Allowed: " + ", ".join(CONSENT_TYPES))
        return v


def rows(body: CustomerImport, now: str):
    m = body.customer.model_dump(mode="json")
    master = {**m, "postal_code_prefix": int(m["postal_code_prefix"]), "record_updated_at": now}
    consents = [{"customer_id": m["customer_id"], "consent_type": t, "status": body.consents.get(t, "not_given"),
                 "updated_at": now, "source": "customer_import",
                 "double_opt_in_confirmed_at": None, "legal_basis": LEGAL_BASIS.get(t, DEFAULT_BASIS)} for t in CONSENT_TYPES]
    return master, consents


def import_customer(engine_ids, body: CustomerImport):
    """Returns a preview; stores the rows unless dry_run. Raises ValueError on a duplicate ID."""
    cid = body.customer.customer_id
    if cid in engine_ids:
        raise ValueError(f"{cid} already exists. Imports only add new customers; existing source data can't be changed.")
    now = dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    master, consents = rows(body, now)
    preview = {"customer": master, "consents": {c["consent_type"]: c["status"] for c in consents},
               "defaulted": [t for t in CONSENT_TYPES if t not in body.consents], "stored": False}
    if body.dry_run:
        return preview
    with db.connect() as c:
        if c.execute("SELECT 1 FROM source_records WHERE source='customer_master' AND customer_id=?", (cid,)).fetchone():
            raise ValueError(f"{cid} already exists.")
        c.execute("INSERT INTO source_records(source,customer_id,payload) VALUES (?,?,?)",
                  ("customer_master", cid, json.dumps(master, ensure_ascii=False)))
        c.executemany("INSERT INTO source_records(source,customer_id,payload) VALUES (?,?,?)",
                      [("consent_status", cid, json.dumps(r, ensure_ascii=False)) for r in consents])
        db.audit(c, "customer_imported", {"customer": master, "consents": preview["consents"], "defaulted": preview["defaulted"]}, cid)
    return {**preview, "stored": True}
