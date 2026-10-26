from types import SimpleNamespace
from app import ai_nba,material_generation,outreach
from test_outreach import material


def test_repairs_stop_after_two_retries_and_keep_nba(monkeypatch):
    calls=[]
    def complete(schema,prompt,packet):
        calls.append(packet)
        return material('Sie erhalten 30 GB.'),{}
    monkeypatch.setattr(ai_nba,'complete',complete)
    packet={'tone':'du','proposal':{'product_id':'P-MO-02'},'channel':'portal_popup','quote':{'target':{'data_gb':30}}}
    result=material_generation.generate(outreach.Material,'instructions',packet,lambda m:outreach.numeric_errors(m,packet['quote'],'portal_popup','du'))
    assert result['status']=='blocked' and len(calls)==3
    assert len(result['attempts'])==3
    assert all(call['proposal']==packet['proposal'] and call['quote']==packet['quote'] for call in calls)
    assert 'errors_to_fix' not in calls[0]
    assert calls[1]['errors_to_fix']==['Copy does not respect Du tone']
    assert calls[2]['previous_material']['body']=='Sie erhalten 30 GB.'
    assert material_generation.explain(result['errors'],'du')[0]['title']=='Mixed forms of address'


def test_repair_success_stops_immediately(monkeypatch):
    calls=[]
    def complete(*args):
        calls.append(args)
        return material('Sie erhalten mehr Daten.' if len(calls)==1 else 'Du erhältst mehr Daten.'),{}
    monkeypatch.setattr(ai_nba,'complete',complete)
    result=material_generation.generate(outreach.Material,'instructions',{},lambda m:outreach.numeric_errors(m,{},'portal_popup','du'))
    assert result['status']=='validated' and len(calls)==2
    assert not result['errors'] and len(result['attempts'])==2


def test_first_valid_draft_needs_no_repairs(monkeypatch):
    calls=[]
    def complete(*args):calls.append(1);return material('Mehr Daten für dich.'),{}
    monkeypatch.setattr(ai_nba,'complete',complete)
    result=material_generation.generate(outreach.Material,'instructions',{},lambda m:[])
    assert result['status']=='validated' and len(calls)==1


def test_provider_failure_stops_without_repeated_requests(monkeypatch):
    calls=[]
    def complete(*args):calls.append(1);raise ai_nba.ProviderError('AI provider timed out')
    monkeypatch.setattr(ai_nba,'complete',complete)
    result=material_generation.generate(outreach.Material,'instructions',{},lambda m:[])
    assert result['status']=='failed' and len(calls)==1
    assert result['material'] is None and result['error']


def test_call_tone_checks_all_spoken_parts_but_not_internal_brief():
    draft=material('Sie hat eine offene Beschwerde.')
    draft.opening='Hallo, passt es gerade für dich?';draft.offer_pitch='Wir kümmern uns um dein Anliegen.';draft.closing='Möchtest du das jetzt klären?'
    draft.discovery_questions=['Was ist bei dir passiert?']
    assert not outreach.numeric_errors(draft,{},'agent_callback','du')
    draft.discovery_questions=['Was wäre für Sie eine gute Lösung?']
    assert 'Copy does not respect Du tone' in outreach.numeric_errors(draft,{},'agent_callback','du')
    draft.discovery_questions=['Was ist bei dir passiert?'];draft.closing='Wir kümmern uns um Ihre Beschwerde.'
    assert 'Copy does not respect Du tone' in outreach.numeric_errors(draft,{},'agent_callback','du')
