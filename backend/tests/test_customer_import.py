"""Uploading one customer: checks first, append-only storage, engine scores the customer before anything is written."""
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app import customer_import as ci, database as db
from app.main import app
from app.service import EngineService

CSV = ('city;household_size;preferred_contact_language;portal_account;app_installed;consent_marketing_email;consent_newsletter_email;'
       'consent_marketing_phone;consent_marketing_sms;consent_portal_app_personalisation;consent_profiling_analytics\n'
       'Offenbach;3;de;ja;nein;granted;not_given;withdrawn;not_given;granted;granted\n')


def errors(content, filename='c.csv', existing=()):
    with pytest.raises(ci.CustomerFileError) as e: ci.parse(filename, content, set(existing))
    return ' '.join(e.value.errors)


def test_csv_and_json_give_the_same_customer():
    c1, k1, _ = ci.parse('c.csv', CSV, set())
    doc = {'customer': {'city': 'Offenbach', 'household_size': 3, 'preferred_contact_language': 'de', 'portal_account': True, 'app_installed': False},
           'consents': {'marketing_email': 'granted', 'newsletter_email': 'not_given', 'marketing_phone': 'withdrawn', 'marketing_sms': 'not_given',
                        'portal_app_personalisation': 'granted', 'profiling_analytics': 'granted'}}
    c2, k2, _ = ci.parse('c.json', json.dumps(doc), set())
    drop = lambda c: {k: v for k, v in c.items() if k != 'record_updated_at'}
    assert drop(c1) == drop(c2) and [x['status'] for x in k1] == [x['status'] for x in k2]
    assert c1['portal_account'] is True and c1['customer_since'] == '2026-09-30'


def test_missing_consent_is_never_granted():
    _, consents, warnings = ci.parse('c.csv', 'city;household_size\nKöln;1\n', set())
    assert {c['status'] for c in consents} == {'not_given'} and len(consents) == 6
    assert any('recorded as not_given' in w for w in warnings)


def test_every_problem_is_reported_at_once():
    msg = errors('city;household_size;preferred_contact_language;consent_marketing_sms\n;99;fr;maybe\n')
    for part in ['city is required', 'household_size must be between 1 and 12', 'de or en', 'consent_marketing_sms']: assert part in msg


@pytest.mark.parametrize('content,expected', [
    ('', 'empty'), ('{"customer": ', 'Invalid JSON'), ('city;household_size\nA;1\nB;2\n', 'exactly one customer'),
    ('customer_id;city;household_size\nMG-100001;A;1\n', 'already exists'), ('customer_id;city;household_size\nX-1;A;1\n', 'MG-100751')])
def test_rejected_files(content, expected):
    assert expected in errors(content, existing={'MG-100001'})


def test_newsletter_without_double_opt_in_warns():
    _, consents, warnings = ci.parse('c.csv', 'city;household_size;consent_newsletter_email\nA;1;granted\n', set())
    assert next(c for c in consents if c['consent_type'] == 'newsletter_email')['double_opt_in_confirmed_at'] is None
    assert any('newsletter channel stays blocked' in w for w in warnings)


def test_templates_parse_cleanly():
    for kind in ('csv', 'json'):
        customer, _, warnings = ci.parse('t.' + kind, ci.template(kind), set())
        assert customer['city'] == 'Offenbach' and not [w for w in warnings if 'unknown' in w.lower()]


@pytest.fixture
def database(tmp_path, monkeypatch):
    source = db.ROOT / 'data/nba.sqlite'
    if not source.exists(): pytest.skip('Local dataset required')
    dest = tmp_path / 'import.sqlite'
    with sqlite3.connect(source) as src, sqlite3.connect(dest) as target: src.backup(target)
    monkeypatch.setenv('NBA_DB_PATH', str(dest));db.initialize()
    return dest


def uploads(path):
    with sqlite3.connect(path) as c: return c.execute("SELECT source,customer_id FROM source_records WHERE origin='upload'").fetchall()


# The local database may already hold customers someone imported, so compare before and after.
def test_dry_run_scores_but_stores_nothing(database):
    before = uploads(database)
    preview, engine = ci.run('c.csv', CSV, lambda rows: EngineService(extra=rows), dry_run=True)
    assert not preview['stored'] and uploads(database) == before
    assert preview['decision']['action'] and engine.customer(preview['customer_id'])['city'] == 'Offenbach'
    assert set(preview['contact_channels']) <= {'email', 'portal_popup', 'app_push'}


def test_store_appends_rows_and_the_new_engine_knows_the_customer(database):
    preview, engine = ci.run('c.csv', CSV, lambda rows: EngineService(extra=rows), dry_run=False)
    cid = preview['customer_id']
    assert preview['stored'] and sorted(s for s, c in uploads(database) if c == cid) == ['consent_status'] * 6 + ['customer_master', 'customer_value']
    assert EngineService().customer(cid)['consent']['marketing_phone']['status'] == 'withdrawn'
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        with db.connect() as c: c.execute("DELETE FROM source_records WHERE origin='upload'")
    with db.connect() as c: assert c.execute("SELECT COUNT(*) FROM audit WHERE kind='customer_imported' AND customer_id=?", (cid,)).fetchone()[0] == 1
    with pytest.raises(ci.CustomerFileError, match='already exists'):
        ci.run('c.csv', 'customer_id;city;household_size\n' + cid + ';A;1\n', lambda rows: EngineService(extra=rows), dry_run=False)


def test_engine_failure_stores_nothing(database):
    def broken(rows): raise RuntimeError('boom')
    before = uploads(database)
    with pytest.raises(ci.CustomerFileError, match='Nothing was stored'): ci.run('c.csv', CSV, broken, dry_run=False)
    assert uploads(database) == before


def test_api_returns_all_errors_as_422():
    response = TestClient(app).post('/api/customers/import', json={'filename': 'c.csv', 'content': 'city;household_size\n;0\n'})
    assert response.status_code == 422
    detail = response.json()['detail']
    assert len(detail['errors']) == 2 and isinstance(detail['warnings'], list)
