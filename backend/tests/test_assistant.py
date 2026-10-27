"""Data assistant: grounded packet, no key handling, and the provider call (with a fake transport)."""
import json
import sqlite3

import httpx
import pytest

from app import assistant, database as db
from app.service import EngineService


@pytest.fixture(scope='module')
def engine(tmp_path_factory):
    source = db.ROOT / 'data/nba.sqlite'
    if not source.exists(): pytest.skip('Local dataset required for assistant checks')
    with pytest.MonkeyPatch.context() as mp:
        dest = tmp_path_factory.mktemp('assistant-db') / 'test.sqlite'
        with sqlite3.connect(source) as src, sqlite3.connect(dest) as target: src.backup(target)
        mp.setenv('NBA_DB_PATH', str(dest))
        db.initialize()
        yield EngineService()


@pytest.fixture
def fake_provider(monkeypatch):
    seen = {}
    def handle(request):
        seen['body'] = json.loads(request.content)
        seen['auth'] = request.headers['authorization']
        return httpx.Response(200, json={'choices': [{'message': {'content': ' 48 customers get a service fix first. '}}]})
    real = httpx.Client
    monkeypatch.setattr(assistant.httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setenv('HAI_API_KEY', 'fixture-key')
    return seen


def test_packet_uses_live_numbers_and_named_customers(engine):
    p = assistant.packet(engine, 'Why is mg-100004 not getting an offer? And MG-999999?')
    assert p['portfolio']['customers'] == len(engine.all())
    assert sum(p['actions_by_type'].values()) == p['portfolio']['customers']
    assert [c['id'] for c in p['customers_asked_about']] == ['MG-100004']
    assert p['customers_asked_about'][0]['decision']['action'] == 'service'
    assert p['unknown_customer_ids'] == ['MG-999999']
    assert p['case_radar']['stuck'][0]['customer_id'] == 'MG-100004'
    assert len(p['catalogue']) == len(engine.catalog)


def test_without_a_key_the_assistant_explains_how_to_connect(engine, monkeypatch):
    monkeypatch.setenv('HAI_API_KEY', '')
    with pytest.raises(assistant.AssistantError, match='Developer area'):
        assistant.answer(engine, [{'role': 'user', 'content': 'How many offers?'}])


def test_answer_sends_data_and_recent_turns(engine, fake_provider):
    turns = [{'role': 'user', 'content': f'q{i}'} if i % 2 == 0 else {'role': 'assistant', 'content': f'a{i}'} for i in range(11)]
    out = assistant.answer(engine, turns)
    assert out == {'answer': '48 customers get a service fix first.'}
    body = fake_provider['body']
    assert fake_provider['auth'] == 'Bearer fixture-key'
    assert body['messages'][0]['role'] == 'system' and '"service_fixes"' in body['messages'][0]['content']
    sent, recent = [m['content'] for m in body['messages'][1:]], [t['content'] for t in turns[-assistant.MAX_TURNS:]]
    assert sent[:-1] == recent[:-1] and sent[-1] == recent[-1] + '\n\n(Answer in English.)'


def test_provider_error_is_reported_not_raised_raw(engine, monkeypatch):
    real = httpx.Client
    monkeypatch.setattr(assistant.httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(lambda r: httpx.Response(500)), **kw))
    monkeypatch.setenv('HAI_API_KEY', 'fixture-key')
    with pytest.raises(assistant.AssistantError, match='HTTP 500'):
        assistant.answer(engine, [{'role': 'user', 'content': 'Hi'}])


def test_named_customer_comes_with_calls_contract_and_portal_visits(engine):
    c = assistant.packet(engine, 'MG-100562 Rechnung nicht angekommen')['customers_asked_about'][0]
    assert c['energy_contracts'][0]['monthly_installment_eur'] > 0
    assert 'dritten Mal' in c['call_transcripts'][0]['transcript']
    assert c['portal_visits'] and c['service_history'][0]['status'] == 'open'


@pytest.mark.parametrize('question, expected', [
    ('MG-100562 rechnung nicht angekommen sagtr der kunder', 'German'),
    ('Warum bekommt MG-100004 kein Angebot?', 'German'),
    ('Was ist los mit MG-100004?', 'German'),
    ('Why is MG-100004 not getting an offer?', 'English'),
    ('What was the uplift?', 'English'),
])
def test_answer_language_follows_the_question(question, expected):
    assert assistant.language(question) == expected
