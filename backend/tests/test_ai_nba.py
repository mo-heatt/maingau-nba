"""Real HTTP adapter tests against the local Postman provider simulation."""
import copy
import json
import os
import sqlite3
from pathlib import Path

import httpx
import pytest

from app import ai_nba, database as db
from app.service import EngineService


@pytest.fixture(scope='module')
def engine(tmp_path_factory):
    source = db.ROOT / 'data/nba.sqlite'
    if not source.exists(): pytest.skip('Local dataset required for full-catalogue integration checks')
    with pytest.MonkeyPatch.context() as mp:
        dest = tmp_path_factory.mktemp('ai-db') / 'test.sqlite'
        with sqlite3.connect(source) as src, sqlite3.connect(dest) as target: src.backup(target)
        mp.setenv('NBA_DB_PATH', str(dest))
        db.initialize()
        with db.connect() as c:
            c.execute('DELETE FROM ai_decisions');c.execute('DELETE FROM ai_batches')
        yield EngineService()


@pytest.fixture
def provider(monkeypatch):
    address = os.getenv('NBA_TEST_PROVIDER_URL')
    if not address: pytest.skip('Start Postman simulation and set NBA_TEST_PROVIDER_URL')
    monkeypatch.setenv('HAI_API_KEY', 'contract-fixture-key')
    monkeypatch.setenv('NBA_AI_BASE_URL', address)
    monkeypatch.setenv('NBA_AI_MODEL', 'fixture')
    monkeypatch.setenv('NBA_AI_TIMEOUT_SECONDS', '5')


def test_full_catalogue_is_not_filtered_by_legacy_signals(engine):
    packet, _ = ai_nba.context(engine, 'MG-100068')
    assert len(packet['catalogue']) == 18
    assert {p['product_id'] for p in packet['catalogue']} == set(engine.catalog.index)
    assert 'P-EN-04' in {p['product_id'] for p in packet['catalogue']}
    assert not any('customer_id' in f['value'] for f in packet['facts'])
    assert 'baseline' not in packet


def test_citations_reject_fabrication_and_allow_exact_subsets():
    packet = {'facts': [{'id':'F1','quote':'{"count": 3}', 'value':{'count':3}}]}
    assert not ai_nba.evidence_errors([ai_nba.Evidence(fact_id='F1',quote='{"count":3}')],packet)
    assert ai_nba.evidence_errors([ai_nba.Evidence(fact_id='F1',quote='{"count":4}')],packet)
    assert ai_nba.evidence_errors([ai_nba.Evidence(fact_id='F1',quote='{"count":true}')],packet)
    assert ai_nba.evidence_errors([ai_nba.Evidence(fact_id='P-EN-01',quote='{}')],packet)


def test_real_http_generation_persists_and_reuses(engine, provider):
    before = engine.customer('MG-100325')['decision']
    result = ai_nba.generate(engine,'MG-100325',refresh=True)
    assert result['status']=='validated', result
    assert result['email'] and result['draft_id']
    assert not result['dispatch_allowed'] and result['review_required']
    assert ai_nba.generate(engine,'MG-100325')['id']==result['id']
    assert ai_nba.latest(engine,'MG-100325')['current']
    assert engine.customer('MG-100325')['decision']==before
    with db.connect() as c:
        draft = dict(c.execute('SELECT * FROM drafts WHERE id=?',(result['draft_id'],)).fetchone())
    assert draft['generator']=='hessian_ai_unreviewed' and draft['status']=='draft'


@pytest.mark.parametrize('model',['invalid-product','bad-evidence'])
def test_unsafe_provider_choice_is_blocked(engine,provider,monkeypatch,model):
    monkeypatch.setenv('NBA_AI_MODEL',model)
    result=ai_nba.generate(engine,'MG-100325',refresh=True)
    assert result['status']=='blocked' and result['validation_errors']
    assert not result['email'] and not result.get('draft_id')


@pytest.mark.parametrize('model',['http-error','malformed','timeout'])
def test_provider_failure_is_saved_without_fallback(engine,provider,monkeypatch,model):
    monkeypatch.setenv('NBA_AI_MODEL',model)
    if model=='timeout':monkeypatch.setenv('NBA_AI_TIMEOUT_SECONDS','0.05')
    result=ai_nba.generate(engine,'MG-100325',refresh=True)
    assert result['status']=='failed' and result['error']
    assert result['proposal'] is None and not result.get('draft_id')


def test_policy_gates_cannot_be_bypassed(engine):
    packet,_=ai_nba.context(engine,'MG-100325')
    packet=copy.deepcopy(packet)
    p=next(p for p in packet['catalogue'] if not p['blocked'] and p['economics'] and p['action_type']!='service')
    evidence=[ai_nba.Evidence(fact_id=f['id'],quote=f['quote']) for f in packet['facts'][:2]]
    proposal=ai_nba.Proposal(action='offer',product_id=p['product_id'],channel='email',need='Need',rationale='Reason',customer_benefit='Benefit',why_now='Now',evidence=evidence,alternatives=[],missing_data=[])
    for forced in ['wait','none','human_review','service']:
        packet['policy']['forced_action']=forced
        assert ai_nba.validate(proposal,packet)
    packet['policy']['forced_action']=None
    proposal.channel='invented-channel'
    assert ai_nba.validate(proposal,packet)


def test_saved_decision_becomes_stale_when_settings_change(engine,provider):
    result=ai_nba.generate(engine,'MG-100325',True)
    assert result['status']=='validated'
    settings=engine.settings();engine.update_settings({'tone_mode':'sie'},settings['version'])
    assert not ai_nba.latest(engine,'MG-100325')['current']


def test_batch_start_is_idempotent(engine):
    job,created=ai_nba.start_batch(engine,3)
    other,again=ai_nba.start_batch(engine,30)
    assert created and not again and job['id']==other['id']
    assert len(job['customer_ids'])==3
