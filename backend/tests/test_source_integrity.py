"""Source consent must not be confused with derived action eligibility."""
import json
import sqlite3
import openpyxl
import pytest
from fastapi.testclient import TestClient
from app import database as db, outreach
from app.ingestion import serial
from app.main import app
from app.snapshot import CustomerSnapshot
from test_outreach import engine


def test_snapshot_is_read_only_and_nested_values_are_detached():
    original={'C':{'consent':{'email':{'status':'granted'}}}}
    snapshot=CustomerSnapshot(original)
    original['C']['consent']['email']['status']='withdrawn'
    copy=snapshot['C'];copy['consent']['email']['status']='not_given'
    assert snapshot['C']['consent']['email']['status']=='granted'
    with pytest.raises(TypeError):snapshot['C']={}


def test_every_imported_consent_matches_workbook(engine):
    wb=openpyxl.load_workbook(db.ROOT/'data/maingau_nba_mockdata.xlsx',read_only=True,data_only=True)
    try:
        rows=iter(wb['consent_status'].values);headers=next(rows)
        source=[{k:serial(v) for k,v in zip(headers,row) if k} for row in rows]
    finally:wb.close()
    with db.connect() as c:
        stored=[json.loads(row[0]) for row in c.execute("SELECT payload FROM source_records WHERE source='consent_status' AND origin='workbook' ORDER BY id")]
    assert source==stored
    for row in source:
        consent=engine.customer(row['customer_id'])['consent'][row['consent_type']]
        assert consent['status']==row['status']
        assert consent['source']==row['source']


def test_holdout_preserves_granted_newsletter_and_portal(engine):
    cid='MG-100126';row=engine.customer(cid)
    assert row['consent']['newsletter_email']['status']=='granted'
    assert row['consent']['portal_app_personalisation']['status']=='granted'
    assert row['decision']['control_group']
    assert {'newsletter_email','portal_popup'}<={p['channel'] for p in row['channels'] if p['allowed']}
    row['consent']['newsletter_email']['status']='withdrawn'
    state=engine.state[cid];state['consent'].clear()
    assert engine.customer(cid)['consent']['newsletter_email']['status']=='granted'
    assert engine.state[cid]['consent']['newsletter_email']['status']=='granted'
    assert not outreach.workspace(engine,cid)['editorial_newsletter_allowed']


def test_imported_records_reject_updates_and_deletes(engine):
    for sql in ["UPDATE source_records SET payload='{}' WHERE source='consent_status'", "DELETE FROM source_records WHERE source='consent_status'"]:
        with pytest.raises(sqlite3.IntegrityError,match='immutable'):
            with db.connect() as c:c.execute(sql)


def test_single_customer_uses_cache_without_copying_all_profiles(engine,monkeypatch):
    engine.all()  # warm the evaluated snapshot
    monkeypatch.setattr(engine,'all',lambda:pytest.fail('Single-customer read must not copy all profiles'))
    assert engine.customer('MG-100126')['id']=='MG-100126'


def test_directory_channel_preview_matches_contact_checks(engine,monkeypatch):
    monkeypatch.setattr(app.state,'engine',engine,raising=False)
    with TestClient(app) as client:
        response=client.get('/api/customers?limit=750')
    assert response.status_code==200
    rows=response.json()['items']
    for row in rows:
        expected=[p['channel'] for p in engine.customer(row['id'])['channels'] if p['allowed']]
        assert row['preview']['contact_channels']==expected
    held=next(r for r in rows if r['id']=='MG-100126')
    assert 'newsletter_email' in held['preview']['contact_channels']
