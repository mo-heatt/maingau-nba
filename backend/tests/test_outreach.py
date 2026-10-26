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
    allowed=[p['channel'] for p in outreach.channel_plans(engine,'MG-100005',d) if p['allowed']]
    assert 'email' not in allowed and 'outbound_call' not in allowed
    with pytest.raises(ValueError,match='not permitted'):
        outreach.generate(engine,'MG-100005',d['id'],'email')
    for ch in allowed[:3]:
        r=outreach.generate(engine,'MG-100005',d['id'],ch)
        assert r['status']=='validated',r
        assert r['channel_eligible'] and not r['dispatch_allowed']
        if ch in ['email','newsletter_email']:assert r['draft_id']
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
        r=outreach.generate(engine,'MG-100005',d['id'],'portal_popup',True)
    assert r['status']=='blocked' and not r['draft_id']
    assert any('Unsupported numeric' in e for e in r['errors'])


def test_workspace_and_generation_share_policy_and_explain_consent(engine,provider,monkeypatch):
    decision=ai_nba.generate(engine,'MG-100005',True)
    workspace=outreach.workspace(engine,'MG-100005')
    allowed={p['channel'] for p in workspace['channels'] if p['allowed']}
    assert allowed==set(workspace['allowed_channels'])
    email=next(p for p in workspace['channels'] if p['channel']=='email')
    assert not email['contact_allowed'] and not email['allowed']
    assert 'marketing_email' in email['contact_reason']
    def unexpected_provider(*args,**kwargs):raise AssertionError('Forbidden channel called the model')
    monkeypatch.setattr(ai_nba,'complete',unexpected_provider)
    for plan in workspace['channels']:
        if not plan['allowed']:
            with pytest.raises(ValueError):outreach.generate(engine,'MG-100005',decision['id'],plan['channel'])


def test_settings_change_invalidates_every_offer_channel(engine,provider,monkeypatch):
    decision=ai_nba.generate(engine,'MG-100005',True)
    settings=engine.settings()
    monkeypatch.setattr(engine,'settings',lambda:{**settings,'version':settings['version']+1,'channels_off':['newsletter_email']})
    workspace=outreach.workspace(engine,'MG-100005')
    assert not workspace['current']
    assert workspace['allowed_channels']==[]
    assert all(not p['allowed'] for p in outreach.channel_plans(engine,'MG-100005',decision))
    assert not workspace['editorial_newsletter_allowed']
    with pytest.raises(ValueError,match='current validated'):
        outreach.generate(engine,'MG-100005',decision['id'],'portal_popup')


def test_consented_channel_can_be_blocked_by_product_value(engine,provider,monkeypatch):
    decision=copy.deepcopy(ai_nba.generate(engine,'MG-100005',True))
    product=next(p for p in decision['context']['catalogue'] if p['product_id']==decision['proposal']['product_id'])
    estimate=next(p for p in product['economics']['per_channel'] if p['channel']=='sms')
    estimate['dclv']=-1
    monkeypatch.setattr(ai_nba,'latest',lambda *args:{'result':decision,'current':True})
    plan=next(p for p in outreach.workspace(engine,'MG-100005')['channels'] if p['channel']=='sms')
    assert plan['contact_allowed'] and not plan['allowed']
    assert plan['reasons']==['Below the channel value threshold']
    def unexpected_provider(*args,**kwargs):raise AssertionError('Blocked channel called the model')
    monkeypatch.setattr(ai_nba,'complete',unexpected_provider)
    with pytest.raises(ValueError,match='value threshold'):
        outreach.generate(engine,'MG-100005',decision['id'],'sms')
