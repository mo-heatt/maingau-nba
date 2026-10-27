import json
import pytest
from fastapi.testclient import TestClient
from app import ai_nba,developer,database as db
from app.main import app
from test_outreach import provider,engine

@pytest.fixture
def clients(provider,monkeypatch):
    monkeypatch.setenv('HAI_API_KEY','server-fixture-key')
    monkeypatch.setattr(developer,'_sessions',{})
    a,b=TestClient(app),TestClient(app)
    yield a,b
    a.close();b.close()


def test_browser_keys_are_isolated_and_never_returned(clients,monkeypatch):
    a,b=clients
    result=a.post('/api/developer/ai',json={'api_key':'alice-fixture-key'})
    assert result.status_code==200,result.text
    assert result.json()['source']=='browser_session'
    assert 'alice-fixture-key' not in result.text
    cookie=result.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert b.get('/api/developer/ai').json()['source']=='server'
    assert b.post('/api/developer/ai',json={'api_key':'bob-fixture-key'}).status_code==200
    observed=[];original=ai_nba.provider_status
    def inspect():observed.append(developer.get_key());return original()
    monkeypatch.setattr(ai_nba,'provider_status',inspect)
    assert a.get('/api/ai/status').status_code==200
    assert b.get('/api/ai/status').status_code==200
    assert observed==['alice-fixture-key','bob-fixture-key']
    assert a.delete('/api/developer/ai').json()['source']=='server'
    assert b.get('/api/developer/ai').json()['session_configured']


def test_rejected_key_keeps_previous_session(clients):
    a,_=clients
    assert a.post('/api/developer/ai',json={'api_key':'valid-fixture-key'}).status_code==200
    token=a.cookies.get(developer.COOKIE)
    denied=a.post('/api/developer/ai',json={'api_key':'rejected-key'})
    assert denied.status_code==400
    assert a.cookies.get(developer.COOKIE)==token
    assert developer.session_key(token)=='valid-fixture-key'
    assert 'rejected-key' not in denied.text


def test_session_expires_without_exposing_or_overwriting_server_key(clients,monkeypatch):
    a,_=clients
    assert a.post('/api/developer/ai',json={'api_key':'expiring-fixture-key'}).status_code==200
    token=a.cookies.get(developer.COOKIE)
    developer._sessions[token].expires=0
    assert a.get('/api/developer/ai').json()['source']=='server'
    assert token not in developer._sessions


def test_invalid_inputs_do_not_echo_secrets(clients):
    a,_=clients
    for payload in [{'api_key':'dummy\x00secret-value'},{'unexpected':'dummy-secret-key'}]:
        response=a.post('/api/developer/ai',json=payload)
        assert response.status_code in (400,422)
        assert 'dummy' not in response.text and 'dummy-secret-key' not in response.text
    response=a.post('/api/developer/ai',json={'api_key':'valid-fixture-key'},headers={'origin':'https://other-site.test'})
    assert response.status_code==403


def test_batch_worker_context_keeps_the_browser_key(engine,monkeypatch):
    observed=[]
    def generate(*args):
        observed.append(developer.get_key())
        return {'id':1,'status':'validated','proposal':{'action':'none','product_id':None}}
    monkeypatch.setattr(ai_nba,'generate',generate)
    job={'customer_ids':['MG-100005','MG-100004'],'completed':0,'total':2,'results':[],'status':'queued'}
    with db.connect() as connection:
        bid=connection.execute('INSERT INTO ai_batches(status,payload) VALUES (?,?)',('queued',json.dumps(job))).lastrowid
    job['id']=bid
    with db.connect() as connection:connection.execute('UPDATE ai_batches SET payload=? WHERE id=?',(json.dumps(job),bid))
    token=developer._active_key.set('batch-fixture-key')
    try:ai_nba.run_batch(engine,bid)
    finally:developer._active_key.reset(token)
    assert observed==['batch-fixture-key','batch-fixture-key']
    with db.connect() as connection:assert connection.execute('SELECT status FROM ai_batches WHERE id=?',(bid,)).fetchone()['status']=='completed'


def test_directory_preview_comes_from_customer_records(engine,monkeypatch):
    monkeypatch.setattr(app.state,'engine',engine,raising=False)
    client=TestClient(app)
    try:
        page=client.get('/api/customers?limit=750').json()
        row=next(c for c in page['items'] if c['id']=='MG-100005')
        profile=engine.customer(row['id'])
        assert row['preview']['products']==profile['products']
        assert row['preview']['open_cases']==len(profile['open_tickets'])
        assert row['preview']['profiling']==profile['profiling']
        assert 'tickets' not in row and 'consent' not in row
    finally:client.close()


def test_local_frontend_origin_is_allowed_but_foreign_sites_are_not(clients):
    a,_=clients
    # Reject malformed keys before any upstream request; dev proxy origin still passes CSRF.
    for origin in ['http://127.0.0.1:5173','http://localhost:5173']:
        response=a.post('/api/developer/ai',json={'api_key':' \n\t\u200b'},headers={'origin':origin})
        assert response.status_code==400
        assert 'valid API key' in response.json()['detail']
    response=a.post('/api/developer/ai',json={'api_key':' \n\t\u200b'},headers={'origin':'https://untrusted.test'})
    assert response.status_code==403


def test_copy_whitespace_is_removed_before_verification(clients):
    a,_=clients
    response=a.post('/api/developer/ai',json={'api_key':' \ufeffsk-fixture- \nkey\u00a0\u200b\u2060'})
    assert response.status_code==200,response.text
    assert developer.session_key(a.cookies.get(developer.COOKIE))=='sk-fixture-key'
    assert 'sk-fixture-key' not in response.text


def test_normalized_rejected_key_keeps_previous_session(clients):
    a,_=clients
    assert a.post('/api/developer/ai',json={'api_key':'valid-fixture-key'}).status_code==200
    token=a.cookies.get(developer.COOKIE)
    response=a.post('/api/developer/ai',json={'api_key':'rejected- \nkey\u200b'})
    assert response.status_code==400
    assert a.cookies.get(developer.COOKIE)==token
    assert developer.session_key(token)=='valid-fixture-key'
    assert 'rejected-key' not in response.text


def test_denied_key_explains_permissions_and_keeps_previous_session(clients):
    a,_=clients
    assert a.post('/api/developer/ai',json={'api_key':'valid-fixture-key'}).status_code==200
    token=a.cookies.get(developer.COOKIE)
    response=a.post('/api/developer/ai',json={'api_key':'forbidden-key'})
    assert response.status_code==400
    assert '(403)' in response.json()['detail'] and 'permissions' in response.json()['detail']
    assert developer.session_key(token)=='valid-fixture-key'
    assert 'forbidden-key' not in response.text
