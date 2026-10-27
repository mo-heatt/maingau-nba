import copy
import pytest
from app import ai_nba,outreach,newsletter,database as db
from app.communication import language,language_errors
from app.email_template import render
from app.engine.content import message
from test_outreach import engine,provider


def test_language_contract_rejects_obvious_wrong_language_without_rejecting_product_names():
    assert language('EN-gb')=='en'
    assert language_errors({'body':'Wir helfen dir gerne, dein offenes Anliegen zu klären.'},'en')
    assert language_errors({'body':'We can help you review your open issue.'},'de')
    assert not language_errors({'headline':'Mobil M','body':'You can review your mobile plan with us.'},'en')
    with pytest.raises(ValueError):language('fr')


def test_english_amounts_and_call_sections_are_validated():
    m=outreach.Material(headline='Help with your issue',subject=None,body='The customer has an open billing issue.',benefit_points=[],opening='Hello, is now convenient?',discovery_questions=['Could you explain what happened?'],offer_pitch='We can help you review the issue.',objections=[],closing='Would you like to discuss the next step?',evidence=[ai_nba.Evidence(fact_id='F1',quote='{}')])
    assert not outreach.numeric_errors(m,{},'agent_callback','sie','en')
    m.body='This costs €99.99.'
    assert any('numeric' in e for e in outreach.numeric_errors(m,{},'sms','du','en'))
    m.body='We will call at 3 pm.'
    assert any('contact time' in e for e in outreach.numeric_errors(m,{},'sms','du','en'))


def test_english_email_localises_fixed_template_and_preserves_tariff_names():
    m={'headline':'More data for you','subject':'Your mobile plan','body':'You can review Mobil M. <script>bad</script>','benefit_points':['More data']}
    q={'product_id':'P-MO-02','product_name':'Mobil Upgrade','current':{'name':'Mobil S','data_gb':10,'monthly_eur':9.99},'target':{'name':'Mobil M','data_gb':30,'monthly_eur':14.99},'delta_monthly_eur':5,'delta_data_gb':20}
    html=render(m,q,'du',language='en')
    for text in ['lang="en"','Selected for you','CURRENT','PROPOSED','/ month','View this offer','Your MAINGAU Team','Mobil M','€14.99']:assert text in html
    for text in ['Für dich','/ Monat','Betreff','<script>']:assert text not in html
    assert '&lt;script&gt;' in html


def test_english_service_template_has_no_sales_cta():
    q={'product_id':'P-SV-01','product_name':'Service-Only / No offer','target':None,'current':None}
    html=render({'headline':'Help with your issue','body':'We can review your issue.'},q,language='en')
    assert 'View service help' in html and 'Demo tariff' not in html


def test_english_baseline_is_not_a_german_template():
    result=message({'language':'en','tone':'du'}, {'pick':{'offer':'P-SV-01','name':'Service','type':'service'}})
    assert result['language']=='en' and 'Hello' in result['body']


def test_customer_language_reaches_generation_and_saved_material(engine,provider):
    cid='MG-100562';decision=ai_nba.generate(engine,cid,True)
    assert decision['context']['policy']['language']=='en'
    result=outreach.generate(engine,cid,decision['id'],'agent_callback',True)
    assert result['status']=='validated',result
    assert result['language']=='en' and 'Hello' in result['material']['opening']
    assert not language_errors(result['material'],'en')
    assert outreach.generate(engine,cid,decision['id'],'agent_callback')['id']==result['id']


def test_legacy_german_copy_is_not_current_for_english_customer(engine,provider):
    cid='MG-100562';decision=ai_nba.generate(engine,cid,True)
    result=outreach.generate(engine,cid,decision['id'],'sms',True)
    old=copy.deepcopy(result);old.pop('language');old['material']['body']='Wir helfen dir beim Anliegen.'
    with db.connect() as c:c.execute('UPDATE outreach_materials SET payload=? WHERE id=?',(__import__('json').dumps(old),result['id']))
    saved=next(r for r in outreach.history(engine,cid)['items'] if r['id']==result['id'])
    assert not saved['current']


def test_wrong_language_stops_after_bounded_repairs(engine,provider,monkeypatch):
    decision=ai_nba.generate(engine,'MG-100562',True)
    original=ai_nba.complete
    def wrong(schema,instructions,packet):
        material,usage=original(schema,instructions,packet)
        material.body='Wir helfen dir gerne mit deinem offenen Anliegen.'
        return material,usage
    monkeypatch.setattr(ai_nba,'complete',wrong)
    result=outreach.generate(engine,'MG-100562',decision['id'],'sms',True)
    assert result['status']=='blocked' and len(result['attempts'])==3
    assert any('English' in e for e in result['errors'])
    assert result['decision_id']==decision['id'] and not result['dispatch_allowed']


def test_editorial_newsletter_uses_english_and_renders_english_html(engine,provider):
    from app.email_template import for_draft
    newsletter.seed()
    cid=next(c['id'] for c in engine.all().values() if c['language']=='en' and newsletter.eligibility(engine,c['id'])['allowed'])
    result=newsletter.generate(engine,cid,'mobile-data-guide','informational',refresh=True)
    assert result['status']=='validated',result
    assert result['language']=='en' and 'helpful update' in result['material']['body']
    with db.connect() as c:draft=c.execute('SELECT * FROM drafts WHERE id=?',(result['draft_id'],)).fetchone()
    html=for_draft(draft)
    assert 'lang="en"' in html and 'Read the article' in html


def test_english_writer_does_not_receive_conflicting_german_examples():
    prompt=outreach.writer_instructions('en','du')
    assert 'passt es gerade kurz für dich' not in prompt
    assert 'Kannst du mir' not in prompt
    assert 'in English' in prompt and 'third-person' in prompt
    assert 'passt es gerade kurz für dich' in outreach.writer_instructions('de','du')
