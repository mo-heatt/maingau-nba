import copy
import json
import sqlite3
from types import SimpleNamespace
import pandas as pd
import pytest
from app import outreach,ai_nba,database as db
from app.service import EngineService


def test_concrete_mobile_quote_uses_supplied_tariffs():
    engine=SimpleNamespace(catalog=pd.DataFrame([{'product_id':'P-MO-02','product_name':'Mobil Upgrade','price_indicative_eur':'+5.00 / month'}]).set_index('product_id'),X={'mobile_contracts':pd.DataFrame([
        {'customer_id':'C','status':'active','plan':'Mobil S','data_volume_gb':10,'monthly_fee_eur':9.99},
        {'customer_id':'X','status':'active','plan':'Mobil M','data_volume_gb':30,'monthly_fee_eur':14.99},
        {'customer_id':'Y','status':'active','plan':'Mobil L','data_volume_gb':100,'monthly_fee_eur':24.99}])})
    q=outreach.quote(engine,'C','P-MO-02')
    assert q['current']=={'name':'Mobil S','data_gb':10,'monthly_eur':9.99}
    assert q['target']=={'name':'Mobil M','data_gb':30,'monthly_eur':14.99}
    assert q['delta_monthly_eur']==5 and q['delta_data_gb']==20
    assert q['demo'] and not q['binding']
    assert 'customer_id' not in json.dumps(q)


def material(body='30 GB für 14,99 € statt 10 GB, zusätzlich 5 €.'):
    return outreach.Material(headline='Mehr Daten',subject='Ein Angebot',body=body,benefit_points=[],opening=None,discovery_questions=[],offer_pitch=None,objections=[],closing=None,evidence=[ai_nba.Evidence(fact_id='F1',quote='{}')])


def test_money_claims_and_tone_are_checked():
    q={'current':{'data_gb':10,'monthly_eur':9.99},'target':{'data_gb':30,'monthly_eur':14.99},'delta_monthly_eur':5,'delta_data_gb':20}
    assert not outreach.numeric_errors(material(),q,'email','du')
    assert outreach.numeric_errors(material('99,99 €'),q,'email','du')
    assert outreach.numeric_errors(material('100 GB'),q,'email','du')
    assert outreach.numeric_errors(material('10 GB in 3 Monaten'),q,'email','du')
    assert outreach.numeric_errors(material('30 €'),q,'email','du')
    assert outreach.numeric_errors(material('14,99 GB'),q,'email','du')
    assert outreach.numeric_errors(material('Du sparst 5 €.'),q,'email','du')
    assert outreach.numeric_errors(material('Wir rufen um 19 Uhr an.'),q,'email','du')
    assert outreach.numeric_errors(material('Du bekommst mehr Daten.'),q,'email','sie')
    assert outreach.numeric_errors(material('Sie bekommen mehr Daten.'),q,'email','du')
    assert outreach.numeric_errors(material('a'*161),q,'sms','du')


@pytest.fixture(scope='module')
def engine(tmp_path_factory):
    source=db.ROOT/'data/nba.sqlite'
    if not source.exists():pytest.skip('Local dataset required')
    with pytest.MonkeyPatch.context() as mp:
        dest=tmp_path_factory.mktemp('outreach')/'test.sqlite'
        with sqlite3.connect(source) as src,sqlite3.connect(dest) as target:src.backup(target)
        mp.setenv('NBA_DB_PATH',str(dest));db.initialize()
        yield EngineService()


@pytest.fixture
def provider(monkeypatch):
    import os
    base=os.getenv('NBA_TEST_PROVIDER_URL')
    if not base:pytest.skip('Start local Postman simulation')
    monkeypatch.setenv('HAI_API_KEY','fixture-key');monkeypatch.setenv('NBA_AI_BASE_URL',base);monkeypatch.setenv('NBA_AI_MODEL','fixture')


def test_dossier_does_not_invent_availability(engine):
    d=outreach.dossier(engine,'MG-100005')
    assert d['availability']['confirmed'] is None
    assert d['availability']['observed_portal_windows']
    assert all(w['observations']>0 for w in d['availability']['observed_portal_windows'])
    limited=copy.copy(engine);old=engine.customer
    limited.customer=lambda cid:{**old(cid),'profiling':False}
    assert outreach.dossier(limited,'MG-100005')['availability']['observed_portal_windows']==[]


def test_channel_material_is_saved_and_never_sent(engine,provider):
    d=ai_nba.generate(engine,'MG-100005',True)
    assert d['status']=='validated'
    for ch in ['email','outbound_call','sms']:
        r=outreach.generate(engine,'MG-100005',d['id'],ch)
        assert r['status']=='validated',r
        assert not r['dispatch_allowed']
        if ch=='email':assert r['draft_id']
        if ch=='outbound_call':assert r['material']['opening'] and not r['channel_eligible']
        assert outreach.generate(engine,'MG-100005',d['id'],ch)['id']==r['id']
    result=outreach.demo_response(engine,'MG-100005',r['id'],'interested')
    assert result['demo'] and not result['contract_created']


def test_fabricated_price_is_blocked(engine,provider,monkeypatch):
    d=ai_nba.generate(engine,'MG-100005',True)
    monkeypatch.setenv('NBA_AI_MODEL','bad-price')
    # Decision context includes the model name; retain model identity while patching only the gateway fixture selection.
    from unittest.mock import patch
    original=ai_nba.provider_status
    with patch.object(ai_nba,'provider_status',side_effect=lambda:{**original(),'model':'fixture'}):
        r=outreach.generate(engine,'MG-100005',d['id'],'email',True)
    assert r['status']=='blocked' and not r['draft_id']
    assert any('Unsupported numeric' in e for e in r['errors'])
