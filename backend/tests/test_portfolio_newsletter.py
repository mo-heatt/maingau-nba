import copy
import json
import pytest
from test_outreach import engine,provider
from app import ai_nba,newsletter,outreach,database as db,portfolio
from app.email_template import for_draft


def test_portfolio_has_all_product_families(engine):
    result=portfolio.products(engine,'MG-100005')
    categories={p['category'] for p in result['items']}
    assert {'electricity','mobile','shop'}<=categories
    assert any(p['name']=='Mobil S' and p['provider']=='MAINGAU' for p in result['items'])
    assert all(p['source'] and p['source_ref'] for p in result['items'])


def test_competing_quote_is_not_an_external_contract(engine):
    read=copy.copy(engine);profile=engine.customer
    read.customer=lambda cid:{**profile(cid),'profiling':True}
    result=portfolio.products(read,'MG-100404')
    quotes=[p for p in result['items'] if p['relationship']=='competing_offer']
    assert quotes and all(p['provider']=='Provider not named' for p in quotes)
    assert all('not established' in p['details']['limitation'] for p in quotes)


def test_recorded_external_product_enters_ai_context(engine):
    _,before=ai_nba.context(engine,'MG-100005')
    payload={'category':'internet','provider':'Example provider','name':'Reported 100 plan','evidence':'Customer statement recorded in test document T1','monthly_eur':29.99}
    result=portfolio.add_external(engine,'MG-100005',payload)
    assert any(p['relationship']=='reported_contract' and p['provider']=='Example provider' for p in result['items'])
    packet,after=ai_nba.context(engine,'MG-100005')
    assert before!=after
    assert any(f['source']=='external_product_records' and f['value']['provider']=='Example provider' for f in packet['facts'])


def test_newsletter_denies_missing_doi_before_model_call(engine,monkeypatch):
    newsletter.seed()
    consent=copy.deepcopy(engine.state['MG-100005']['consent'])
    consent['newsletter_email']['doi']=None
    monkeypatch.setitem(engine.state['MG-100005'],'consent',consent)
    monkeypatch.setattr(ai_nba,'complete',lambda *a:pytest.fail('Forbidden channel must not call provider'))
    with pytest.raises(ValueError,match='not permitted'):newsletter.generate(engine,'MG-100005','mobile-data-guide','informational')


def test_informational_newsletter_does_not_need_nba(engine,provider,monkeypatch):
    newsletter.seed()
    monkeypatch.setattr(ai_nba,'latest',lambda *a:{'result':None,'current':False})
    ctx=newsletter.context(engine,'MG-100005')
    assert ctx['eligibility']['allowed'] and not ctx['offer_allowed']
    result=newsletter.generate(engine,'MG-100005','mobile-data-guide','informational',refresh=True)
    assert result['status']=='validated',result
    assert result['draft_id'] and result['decision_id'] is None and not result['dispatch_allowed']
    with db.connect() as c:draft=c.execute('SELECT * FROM drafts WHERE id=?',(result['draft_id'],)).fetchone()
    html=for_draft(draft)
    assert 'Artikel lesen' in html and 'Dieses Angebot ansehen' not in html
    assert '2023-07-27' in html and 'datenvolumen-was-ist-das' in html


def test_news_led_offer_uses_validated_quote(engine,provider):
    newsletter.seed();d=ai_nba.generate(engine,'MG-100005',True)
    result=newsletter.generate(engine,'MG-100005','smart-meter-guide','offer',d['id'],True)
    assert result['status']=='validated',result
    assert result['quote']['product_id']==d['proposal']['product_id']
    assert result['draft_id']


def test_unknown_or_nonofficial_news_source_is_rejected(engine):
    with pytest.raises(ValueError,match='official'):
        newsletter.add_article({'title':'Unverified','published_at':'2026-10-26','url':'https://maingau-energie.de.evil.test/news','summary':'Untrusted source summary'})


def test_article_id_alias_requires_matching_source_fields():
    source={'id':'N1','value':{'id':'smart-meter-guide','title':'Smart Meter','summary':'Verified facts'},'quote':'unused'}
    def draft(ref,quote):
        return newsletter.Copy(headline='Update',subject='Update',body='Information',benefit_points=[],evidence=[ai_nba.Evidence(fact_id=ref,quote=quote)])
    copy=newsletter.normalise_editorial_reference(draft('smart-meter-guide','{"title":"Smart Meter"}'),source)
    assert copy.evidence[0].fact_id=='N1'
    assert not ai_nba.evidence_errors(copy.evidence,{'facts':[source]})
    for ref in ('N1','smart-meter-guide'):
        exact=newsletter.normalise_editorial_reference(draft(ref,'Verified facts'),source)
        assert exact.evidence[0].fact_id=='N1'
        assert not ai_nba.evidence_errors(exact.evidence,{'facts':[source]})
    for ref,quote in [('smart-meter-guide','{"title":"Invented"}'),('other-guide','{"title":"Smart Meter"}'),('smart-meter-guide','{}'),('N1','Verified'),('N1','Changed facts')]:
        copy=newsletter.normalise_editorial_reference(draft(ref,quote),source)
        assert ai_nba.evidence_errors(copy.evidence,{'facts':[source]})
