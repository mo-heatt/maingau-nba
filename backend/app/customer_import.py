"""Create one customer from an uploaded CSV or JSON file.

The upload is parsed and checked first; nothing is written unless every check passes.
Rows are appended to source_records (origin='upload') like workbook rows, never updated.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import re
import statistics
from . import database as db
from .engine.constants import SNAPSHOT

MAX_BYTES = 100_000
CONSENTS = ['newsletter_email', 'marketing_email', 'marketing_phone', 'marketing_sms', 'portal_app_personalisation', 'profiling_analytics']
STATUSES = {'granted': 'granted', 'not_given': 'not_given', 'withdrawn': 'withdrawn',
            'yes': 'granted', 'ja': 'granted', 'true': 'granted', '1': 'granted',
            'no': 'not_given', 'nein': 'not_given', 'false': 'not_given', '0': 'not_given', '': None}
LEGAL_BASIS = 'consent (Art. 6(1)(a) GDPR, §7 UWG)'
ID = re.compile(r'^MG-\d{6}$')
TRUE, FALSE = {'true', 'yes', 'ja', '1', 'x'}, {'false', 'no', 'nein', '0', ''}


class CustomerFileError(ValueError):
    """Raised with the full list of problems so the user can fix the file in one go."""
    def __init__(self, errors, warnings=()):
        super().__init__('; '.join(errors));self.errors=list(errors);self.warnings=list(warnings)


def template(kind):
    """Example file the dialog offers for download."""
    row = {'customer_id': '', 'city': 'Offenbach', 'household_size': 2, 'preferred_contact_language': 'de', 'birth_year': 1988,
           'postal_code_prefix': 630, 'customer_since': SNAPSHOT.date().isoformat(), 'portal_account': True, 'app_installed': False,
           **{'consent_' + k: 'granted' if k in ('marketing_email', 'portal_app_personalisation', 'profiling_analytics') else 'not_given' for k in CONSENTS},
           'newsletter_double_opt_in_at': ''}
    if kind == 'json':
        return json.dumps({'customer': {k: v for k, v in row.items() if not k.startswith(('consent_', 'newsletter_'))},
                           'consents': {k: row['consent_' + k] for k in CONSENTS}, 'newsletter_double_opt_in_at': None}, indent=2, ensure_ascii=False)
    out = io.StringIO();w = csv.DictWriter(out, fieldnames=list(row), delimiter=';');w.writeheader();w.writerow(row);return out.getvalue()


def _rows(filename, content):
    if len(content.encode()) > MAX_BYTES: raise CustomerFileError([f'File is larger than {MAX_BYTES // 1000} KB.'])
    text = content.lstrip('﻿').strip()
    if not text: raise CustomerFileError(['The file is empty.'])
    if filename.lower().endswith('.json') or text[:1] in '{[':
        try: data = json.loads(text)
        except json.JSONDecodeError as e: raise CustomerFileError([f'Invalid JSON (line {e.lineno}): {e.msg}.'])
        items = data if isinstance(data, list) else [data]
        flat = []
        for item in items:
            if not isinstance(item, dict): raise CustomerFileError(['Each JSON customer must be an object.'])
            row = {**item.get('customer', {}), **{k: v for k, v in item.items() if k not in ('customer', 'consents')}}
            for k, v in (item.get('consents') or {}).items(): row['consent_' + k] = v
            flat.append(row)
        return flat
    try: dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=',;\t')
    except csv.Error: dialect = csv.excel
    return [{(k or '').strip(): (v or '').strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text), dialect=dialect)]


def _bool(v, name, errors):
    if isinstance(v, bool): return v
    s = str(v if v is not None else '').strip().lower()
    if s in TRUE: return True
    if s in FALSE: return False
    errors.append(f'{name} must be yes/no, got "{v}".');return False


def _int(v, name, lo, hi, errors, required=False):
    if v in (None, ''):
        if required: errors.append(f'{name} is required.')
        return None
    try: n = int(str(v).strip())
    except ValueError: errors.append(f'{name} must be a whole number, got "{v}".');return None
    if not lo <= n <= hi: errors.append(f'{name} must be between {lo} and {hi}, got {n}.')
    return n


def _date(v, name, errors):
    if v in (None, ''): return None
    try: return dt.date.fromisoformat(str(v).strip()[:10])
    except ValueError: errors.append(f'{name} must be a date like 2026-09-30, got "{v}".')


def parse(filename, content, existing_ids):
    """Return (customer, consents, warnings) or raise CustomerFileError listing every problem."""
    rows = _rows(filename, content);errors, warnings = [], []
    if len(rows) != 1: raise CustomerFileError([f'The file contains {len(rows)} customers. This import creates exactly one customer per file.'])
    r = rows[0];today = dt.date.today()
    known = {'customer_id', 'city', 'household_size', 'preferred_contact_language', 'birth_year', 'postal_code_prefix', 'customer_since',
             'portal_account', 'app_installed', 'newsletter_double_opt_in_at', *('consent_' + k for k in CONSENTS)}
    if unknown := sorted(k for k in r if k and k not in known): warnings.append('Ignored unknown fields: ' + ', '.join(unknown) + '.')

    cid = str(r.get('customer_id') or '').strip().upper()
    if cid and not ID.match(cid): errors.append(f'customer_id must look like MG-100751, got "{cid}".')
    elif cid in existing_ids: errors.append(f'Customer {cid} already exists. Existing customers are never overwritten.')
    city = str(r.get('city') or '').strip()
    if not city: errors.append('city is required.')
    elif len(city) > 60: errors.append('city is longer than 60 characters.')
    household = _int(r.get('household_size'), 'household_size', 1, 12, errors, required=True)
    lang = str(r.get('preferred_contact_language') or 'de').strip().lower()
    if lang not in ('de', 'en'): errors.append(f'preferred_contact_language must be de or en, got "{lang}".')
    birth = _int(r.get('birth_year'), 'birth_year', 1900, today.year - 18, errors)
    postal = _int(r.get('postal_code_prefix'), 'postal_code_prefix', 0, 999, errors)
    since = _date(r.get('customer_since'), 'customer_since', errors) or SNAPSHOT.date()
    if since > today: errors.append('customer_since cannot be in the future.')
    portal = _bool(r.get('portal_account'), 'portal_account', errors);app = _bool(r.get('app_installed'), 'app_installed', errors)
    if app and not portal: warnings.append('App installed without a portal account: app push and pop-ups depend on account availability.')

    now = dt.datetime.now().replace(microsecond=0).isoformat(sep=' ')
    doi = _date(r.get('newsletter_double_opt_in_at'), 'newsletter_double_opt_in_at', errors)
    consents, missing = [], []
    for kind in CONSENTS:
        raw = r.get('consent_' + kind);key = str(raw if raw is not None else '').strip().lower()
        if key not in STATUSES: errors.append(f'consent_{kind} must be granted, not_given or withdrawn, got "{raw}".');continue
        status = STATUSES[key]
        if status is None: missing.append(kind);status = 'not_given'
        consents.append({'customer_id': None, 'consent_type': kind, 'status': status, 'updated_at': now, 'source': 'data_import',
                         'double_opt_in_confirmed_at': doi.isoformat() + ' 00:00:00' if kind == 'newsletter_email' and status == 'granted' and doi else None,
                         'legal_basis': LEGAL_BASIS})
    if missing: warnings.append('No consent given in the file for ' + ', '.join(missing) + ': recorded as not_given.')
    if any(c['consent_type'] == 'newsletter_email' and c['status'] == 'granted' for c in consents) and not doi:
        warnings.append('Newsletter consent without double opt-in date: the newsletter channel stays blocked.')
    if errors: raise CustomerFileError(errors, warnings)
    customer = {'customer_id': cid or None, 'customer_type': 'B2C', 'customer_since': since.isoformat(), 'birth_year': birth,
                'postal_code_prefix': postal, 'city': city, 'household_size': household, 'portal_account': portal, 'app_installed': app,
                'preferred_contact_language': lang, 'record_updated_at': now}
    return customer, consents, warnings


def _next_id(c):
    ids = [r[0] for r in c.execute("SELECT customer_id FROM source_records WHERE source='customer_master'") if r[0] and ID.match(r[0])]
    return f'MG-{max([int(i[3:]) for i in ids] or [100000]) + 1}'


def _value(c, cid):
    """A new customer has no contracts yet: no margin or cost; churn starts at the portfolio median. Marked as a default."""
    churn = [json.loads(r[0]).get('churn_prob_12m') for r in c.execute("SELECT payload FROM source_records WHERE source='customer_value'")]
    churn = [float(v) for v in churn if isinstance(v, (int, float))]
    return {'customer_id': cid, 'active_business_lines': 0, 'annual_margin_eur': 0.0, 'cost_to_serve_12m_eur': 0.0, 'service_cost_12m_eur': 0.0,
            'churn_prob_12m': round(statistics.median(churn), 3) if churn else 0.15, 'churn_drivers': None, 'clv_eur': 0.0,
            'clv_service_impact_eur': 0.0, 'clv_calc_date': SNAPSHOT.date().isoformat(), 'model_version': 'new_customer_default_v1'}


def run(filename, content, build, dry_run=True):
    """Check the file and score the customer with build(rows) -> engine; store only if dry_run is False.

    Scoring happens before the commit: stored rows can never be removed again, so a customer the engine
    cannot evaluate must not be written. Returns (preview, engine)."""
    with db.connect() as c:
        # Take the write lock before reading IDs, so two uploads cannot claim the same next ID.
        if not dry_run: c.execute('BEGIN IMMEDIATE')
        existing = {r[0] for r in c.execute("SELECT customer_id FROM source_records WHERE source='customer_master'")}
        customer, consents, warnings = parse(filename, content, existing)
        cid = customer['customer_id'] or _next_id(c);customer['customer_id'] = cid
        for row in consents: row['customer_id'] = cid
        value = _value(c, cid)
        rows = [('customer_master', customer), ('customer_value', value), *(('consent_status', r) for r in consents)]
        try:
            engine = build(rows);profile = engine.customer(cid)
        except Exception as exc:
            raise CustomerFileError([f'The engine could not evaluate this customer ({type(exc).__name__}). Nothing was stored.'], warnings)
        d = profile['decision']
        preview = {'customer_id': cid, 'customer': customer, 'consents': {r['consent_type']: r['status'] for r in consents},
                   'value': value, 'warnings': warnings, 'stored': False,
                   'decision': {'action': d['action'], 'name': d['name'], 'reason': d['reason'], 'expected_gain_eur': d['expected_gain_eur']},
                   'contact_channels': [ch['channel'] for ch in profile['channels'] if ch['allowed']]}
        if dry_run: return preview, engine
        c.executemany("INSERT INTO source_records(source,customer_id,payload,origin) VALUES (?,?,?,'upload')",
                      [(s, cid, json.dumps(p, ensure_ascii=False)) for s, p in rows])
        db.audit(c, 'customer_imported', {'file': filename, 'sha256': hashlib.sha256(content.encode()).hexdigest(), 'warnings': warnings}, cid)
    return {**preview, 'stored': True}, engine
