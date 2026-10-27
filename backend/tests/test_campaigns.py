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
    assert a['eligible'] + sum(r['customers'] for r in a['left_out']) == a['targeted']
    assert a['contactable'] == sum(seg['customers'] for seg in a['segments'] if seg['included'])
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


MOBILE = {'name': 'Mobile autumn', 'goal': 'Win energy customers for a mobile contract', 'offer': 'P-MO-01'}


def test_every_customer_gets_their_own_best_allowed_channel(client):
    from app.main import engine
    from app.campaigns import audience
    a = audience(engine(), MOBILE)
    assert len({m['channel'] for m in a['_members']}) > 1
    for m in a['_members'][:40]:
        r = engine().customer(m['id'])
        option = next(o for o in r['candidates'] if o['offer'] == 'P-MO-01')
        allowed = {c['channel'] for c in r['channels'] if c['allowed']}
        best = max((c for c in option['per_channel'] if c['channel'] in allowed), key=lambda c: c['dclv'])
        assert m['channel'] == best['channel'] and m['tone'] == r['tone'] and m['reason'] == option['why']


def test_segments_can_be_switched_on_and_off(client):
    segs = client.post('/api/campaigns/preview', json=MOBILE).json()['segments']
    one = segs[0]['key']
    a = client.post('/api/campaigns/preview', json={**MOBILE, 'segments': [one]}).json()
    assert [s['key'] for s in a['segments'] if s['included']] == [one] and a['contactable'] == segs[0]['customers']
    assert all('de-sie' in s['messages'] or 'de-du' in s['messages'] or 'en-sie' in s['messages'] or 'en-du' in s['messages'] for s in segs)


def test_suggestions_fall_back_to_rules_without_a_key(client, monkeypatch):
    monkeypatch.setenv('HAI_API_KEY', '')
    s = client.post('/api/campaigns/suggest', json=MOBILE).json()
    assert s['source'] == 'rules' and s['summary'] and s['segments'] and 'Developer area' in s['note']
    assert {a['segment'] for a in s['segments']} <= {seg['key'] for seg in client.post('/api/campaigns/preview', json=MOBILE).json()['segments']}


def test_running_campaign_has_timeline_breakdowns_insights_and_a_follow_up(client):
    created = client.post('/api/campaigns', json=MOBILE).json()
    running = client.post(f"/api/campaigns/{created['id']}/launch").json()
    t = running['tracking']
    assert t['timeline'][-1]['sent'] == t['sent'] and len(t['timeline']) == t['days']
    assert sum(s['sent'] for s in t['segments']) == t['sent'] == sum(c['sent'] for c in t['channels'])
    assert running['insights'] and all(i['kind'] in ('good', 'warn', 'idea') for i in running['insights'])
    follow = client.post(f"/api/campaigns/{created['id']}/follow-up").json()
    dropped = {i['drop'] for i in running['insights'] if i.get('drop')}
    assert follow['status'] == 'draft' and follow['follows'] == created['id'] and not dropped & set(follow['segments'])
    assert client.post(f"/api/campaigns/{follow['id']}/follow-up").status_code == 409
