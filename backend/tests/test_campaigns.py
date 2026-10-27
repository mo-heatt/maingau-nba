"""Campaigns: the audience follows the engine's rules, drafts launch once, and tracking is simulated and stable."""
import os
import sqlite3

import pytest

from app import database as db

SPEC = {'name': 'Autumn StromGarant', 'offer': 'P-EN-02', 'channel': 'newsletter_email', 'value_tier': ['High value (top 20 %)']}


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    source = db.ROOT / 'data/nba.sqlite'
    if not source.exists(): pytest.skip('Local dataset required for campaign checks')
    dest = tmp_path_factory.mktemp('campaign-db') / 'test.sqlite'
    with sqlite3.connect(source) as src, sqlite3.connect(dest) as target: src.backup(target)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('NBA_DB_PATH', str(dest))
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            yield c


def test_every_targeted_customer_is_contactable_or_has_a_reason(client):
    a = client.post('/api/campaigns/preview', json=SPEC).json()
    assert 0 < a['targeted'] < a['total']
    assert a['contactable'] + sum(r['customers'] for r in a['left_out']) == a['targeted']
    assert {r['reason'] for r in a['left_out']} <= {'control', 'not_relevant', 'exclusion', 'profiling', 'channel', 'limit'}


def test_contactable_customers_have_consent_on_the_channel_and_no_exclusion(client):
    from app.main import engine
    from app.campaigns import audience
    a = audience(engine(), {**SPEC, 'value_tier': []})
    for m in a['_members']:
        if m['control']: continue
        r = engine().customer(m['id'])
        assert next(c for c in r['channels'] if c['channel'] == SPEC['channel'])['allowed']
        assert not r['decision']['control_group']
        assert not next(o for o in r['candidates'] if o['offer'] == SPEC['offer'])['blocked']


def test_draft_launches_once_and_tracking_is_simulated_and_stable(client):
    created = client.post('/api/campaigns', json=SPEC).json()
    assert created['status'] == 'draft' and created['tracking'] is None
    running = client.post(f"/api/campaigns/{created['id']}/launch").json()
    t = running['tracking']
    assert running['status'] == 'running' and t['simulated'] is True
    assert t['sent'] == running['audience']['contactable'] and t['yes'] <= t['seen'] <= t['sent']
    again = next(c for c in client.get('/api/campaigns').json()['items'] if c['id'] == created['id'])
    assert again['tracking'] == t
    assert client.post(f"/api/campaigns/{created['id']}/launch").status_code == 409
    assert client.delete(f"/api/campaigns/{created['id']}").status_code == 409


def test_drafts_can_be_deleted(client):
    created = client.post('/api/campaigns', json={**SPEC, 'name': 'Throwaway'}).json()
    assert client.delete(f"/api/campaigns/{created['id']}").status_code == 200
    assert created['id'] not in {c['id'] for c in client.get('/api/campaigns').json()['items']}
    assert client.delete(f"/api/campaigns/{created['id']}").status_code == 404


@pytest.mark.parametrize('change', [{'offer': 'P-SV-01'}, {'offer': 'P-XX-99'}, {'channel': 'agent_callback'}, {'city': ['Atlantis']}, {'starts': '2026-11-30', 'ends': '2026-11-01'}])
def test_invalid_campaigns_are_rejected(client, change):
    assert client.post('/api/campaigns', json={**SPEC, **change}).status_code == 409
