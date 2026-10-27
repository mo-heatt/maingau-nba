from app import ai_nba,outreach
from test_outreach import engine,provider


def test_service_callback_is_recommended_not_exclusive(engine,provider):
    cid='MG-100562';decision=ai_nba.generate(engine,cid,True)
    assert decision['status']=='validated' and decision['proposal']['action']=='service'
    plans={p['channel']:p for p in outreach.channel_plans(engine,cid,decision)}
    assert plans['agent_callback']['recommended'] and plans['agent_callback']['allowed']
    for channel in ['sms','outbound_call']:
        assert plans[channel]['contact_allowed']
        assert plans[channel]['allowed'] and not plans[channel]['recommended']
        assert plans[channel]['advisories'] and plans[channel]['reasons']==[]
    assert not plans['email']['allowed']  # missing actual consent remains a gate


def test_service_sms_can_be_generated_without_changing_nba(engine,provider):
    cid='MG-100562';decision=ai_nba.generate(engine,cid,True)
    result=outreach.generate(engine,cid,decision['id'],'sms',True)
    assert result['status']=='validated',result
    assert result['channel_eligible'] and not result['dispatch_allowed']
    assert result['quote']['product_id']=='P-SV-01'
    assert result['decision_id']==decision['id']
    assert len(result['material']['body'])<=160
    assert result['language']=='en' and 'issue' in result['material']['body']
    assert 'Anliegen' not in result['material']['body']
    assert ai_nba.latest(engine,cid)['result']['id']==decision['id']


def test_explicit_channel_disable_still_blocks_service_alternative(engine,provider,monkeypatch):
    cid='MG-100562';decision=ai_nba.generate(engine,cid,True);settings=engine.settings()
    # Keep a current proposal to isolate the explicit channel policy check.
    monkeypatch.setattr(ai_nba,'latest',lambda *args:{'current':True,'result':decision})
    monkeypatch.setattr(engine,'settings',lambda:{**settings,'channels_off':['sms']})
    plan=next(p for p in outreach.channel_plans(engine,cid,decision) if p['channel']=='sms')
    assert not plan['allowed'] and 'Channel disabled by marketing' in plan['reasons']
