import json
from contextlib import asynccontextmanager
from typing import Dict, List, Literal, Optional
from pathlib import Path
from datetime import date
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import database as db
from .ingestion import import_sources
from .service import EngineService, safe
from .replay import preview
from . import ai_nba, outreach, portfolio, newsletter
from .insights import customer_insights
from .email_template import for_draft

@asynccontextmanager
async def lifespan(app):
    db.initialize();newsletter.seed();import_sources();app.state.engine=EngineService()
    with db.connect() as c:
        c.execute("UPDATE ai_batches SET status='interrupted' WHERE status IN ('queued','running')")
    yield

app=FastAPI(title='MAINGAU NBA',version='1.0.0',lifespan=lifespan,docs_url='/api/docs',openapi_url='/api/openapi.json',redoc_url=None)

def engine():return app.state.engine

def call(fn,*args):
    try:return fn(*args)
    except KeyError:raise HTTPException(404,'Customer not found')
    except ValueError as exc:raise HTTPException(409,str(exc))

class Settings(BaseModel):
    version:int=Field(ge=1)
    contact_cap_30d:int=Field(ge=1,le=10)
    min_dclv_eur:float=Field(ge=0,le=10000)
    tone_mode:Literal['mirror','sie']='mirror'
    offers_off:List[str]=[]
    channels_off:List[str]=[]
    priorities:Dict[str,Literal['low','normal','high']]={}
    content_approvals:Dict[str,Dict[Literal['du','sie'],bool]]={}

class Review(BaseModel):
    decision_id:str
    status:Literal['approved','rejected']
    note:str=Field(default='',max_length=500)

class Override(BaseModel):
    offer_id:Optional[str]=None
    note:str=Field(default='',max_length=500)

@app.get('/api/health')
def health():return {'status':'ok','customers':len(engine().state),'decision_engine':'single_python_engine','delivery':'disabled','snapshot':'2026-09-30T23:59:00'}

@app.get('/api/settings')
def settings():return engine().settings()

@app.patch('/api/settings')
def update_settings(body:Settings):
    data=body.model_dump();version=data.pop('version');return call(engine().update_settings,data,version)

@app.get('/api/catalog')
def catalog():
    from .engine.constants import CHANNELS
    from .engine.templates import TEMPLATES
    return {'products':safe(engine().X['product_catalog'].to_dict(orient='records')),'channels':list(CHANNELS),'templates':TEMPLATES}

@app.get('/api/customers')
def customers(q:str='',action:Optional[str]=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=750)):
    rows=list(engine().all().values());rows=[r for r in rows if q.lower() in (r['id']+' '+r['city']).lower() and (not action or r['decision']['action']==action)]
    rows.sort(key=lambda r:(-r['decision']['expected_gain_eur'],r['id']))
    return {'total':len(rows),'offset':offset,'limit':limit,'items':[{k:r[k] for k in ['id','city','since','value','decision']} for r in rows[offset:offset+limit]]}

@app.get('/api/customers/{cid}')
def customer(cid:str):return call(engine().customer,cid)

class ExternalProduct(BaseModel):
    category:Literal['electricity','gas','mobile','internet','charging','devices','other']
    provider:str=Field(min_length=1,max_length=120)
    name:str=Field(min_length=1,max_length=150)
    evidence:str=Field(min_length=8,max_length=1500)
    monthly_eur:Optional[float]=Field(default=None,ge=0,le=10000)

@app.get('/api/customers/{cid}/products')
def customer_products(cid:str):return call(portfolio.products,engine(),cid)

@app.post('/api/customers/{cid}/external-products')
def external_product(cid:str,body:ExternalProduct):return call(portfolio.add_external,engine(),cid,body.model_dump())

@app.get('/api/customers/{cid}/insights')
def insights(cid:str):return call(customer_insights,engine(),cid)

@app.post('/api/customers/{cid}/reviews')
def review(cid:str,body:Review):return call(engine().review,cid,body.decision_id,body.status,body.note)

@app.post('/api/customers/{cid}/override')
def override(cid:str,body:Override):return call(engine().override,cid,body.offer_id,body.note)

@app.get('/api/marketing')
def marketing():return engine().marketing()

@app.get('/api/replay')
def replay():return preview(engine())

@app.get('/api/audit')
def audit(limit:int=Query(50,ge=1,le=500)):
    with db.connect() as c:return {'items':[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT ?',(limit,))]}

@app.post('/api/customers/{cid}/drafts')
def draft(cid:str):
    row=call(engine().customer,cid);decision=row['decision'];m=decision['message']
    if not m or decision['action'] not in ['offer','service']:raise HTTPException(409,'No actionable message')
    with db.connect() as c:
        cursor=c.execute('INSERT INTO drafts(customer_id,decision_id,subject,body,generator) VALUES (?,?,?,?,?)',(cid,decision['id'],m['subject'],m['body'],'approved_template'))
        did=cursor.lastrowid;db.audit(c,'draft_created',{'draft_id':did,'decision_id':decision['id']},cid)
    return {'id':did,'subject':m['subject'],'body':m['body'],'generator':'approved_template','sent':False}

@app.get('/api/drafts/{did}/download')
def download(did:int):
    from email.message import EmailMessage
    with db.connect() as c:r=c.execute('SELECT * FROM drafts WHERE id=?',(did,)).fetchone()
    if not r:raise HTTPException(404,'Draft not found')
    m=EmailMessage();m['Subject']=r['subject'];m['From']='MAINGAU Demo <demo@example.invalid>';m['To']=r['customer_id'].lower()+'@example.invalid';m['X-Unsent']='1';m.set_content(r['body']+'\n\nHackathon demo. Synthetic data. No message has been sent.')
    html=for_draft(r)
    if html:m.add_alternative(html,subtype='html')
    return Response(m.as_bytes(),media_type='message/rfc822',headers={'Content-Disposition':f'attachment; filename="maingau-{did}.eml"'})

@app.get('/api/drafts/{did}/preview')
def draft_preview(did:int):
    with db.connect() as c:r=c.execute('SELECT * FROM drafts WHERE id=?',(did,)).fetchone()
    if not r:raise HTTPException(404,'Draft not found')
    html=for_draft(r)
    if not html:raise HTTPException(409,'No HTML template for this draft')
    return Response(html,media_type='text/html',headers={'Content-Security-Policy':"default-src 'none'; img-src https://cdn0.scrvt.com; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",'Referrer-Policy':'no-referrer'})

class AIGenerate(BaseModel):
    refresh:bool=False

class AIBatch(BaseModel):
    limit:int=Field(default=30,ge=1,le=50)

@app.get('/api/ai/status')
def ai_status():return ai_nba.provider_status()

@app.get('/api/customers/{cid}/ai-context')
def ai_context(cid:str):
    packet,fingerprint=call(ai_nba.context,engine(),cid)
    return {'context':packet,'input_hash':fingerprint}

@app.get('/api/customers/{cid}/ai-nba')
def ai_latest(cid:str):return call(ai_nba.latest,engine(),cid)

@app.post('/api/customers/{cid}/ai-nba')
def ai_generate(cid:str,body:AIGenerate):
    if not ai_nba.provider_status()['configured']:raise HTTPException(503,'Hessian AI key is not configured')
    return call(ai_nba.generate,engine(),cid,body.refresh)

@app.get('/api/ai/batches/latest')
def ai_batch_latest():return ai_nba.batch_latest()

@app.post('/api/ai/batches')
def ai_batch(body:AIBatch,background:BackgroundTasks):
    if not ai_nba.provider_status()['configured']:raise HTTPException(503,'Hessian AI key is not configured')
    job,created=ai_nba.start_batch(engine(),body.limit)
    if created:background.add_task(ai_nba.run_batch,engine(),job['id'])
    return job

class NewsSource(BaseModel):
    title:str=Field(min_length=5,max_length=200)
    published_at:date
    url:str=Field(max_length=500)
    summary:str=Field(min_length=20,max_length=1800)

class NewsletterRequest(BaseModel):
    article_id:str
    mode:Literal['informational','offer']='informational'
    decision_id:Optional[int]=None
    refresh:bool=False

@app.post('/api/news')
def add_news(body:NewsSource):return call(newsletter.add_article,body.model_dump(mode='json'))

@app.get('/api/customers/{cid}/newsletter-context')
def newsletter_context(cid:str):return call(newsletter.context,engine(),cid)

@app.get('/api/customers/{cid}/newsletters')
def newsletter_history(cid:str):return call(newsletter.history,engine(),cid)

@app.post('/api/customers/{cid}/newsletters')
def newsletter_generate(cid:str,body:NewsletterRequest):return call(newsletter.generate,engine(),cid,body.article_id,body.mode,body.decision_id,body.refresh)

class OutreachRequest(BaseModel):
    decision_id:int=Field(ge=1)
    channel:Literal['email','newsletter_email','outbound_call','agent_callback','sms','app_push','portal_popup']
    refresh:bool=False

@app.get('/api/customers/{cid}/outreach-context')
def outreach_context(cid:str):return call(outreach.workspace,engine(),cid)

@app.get('/api/customers/{cid}/outreach')
def outreach_history(cid:str):return call(outreach.history,engine(),cid)

@app.post('/api/customers/{cid}/outreach')
def outreach_generate(cid:str,body:OutreachRequest):
    return call(outreach.generate,engine(),cid,body.decision_id,body.channel,body.refresh)

class OfferResponse(BaseModel):
    response:Literal['interested','not_now']

@app.post('/api/customers/{cid}/outreach/{mid}/response')
def offer_response(cid:str,mid:int,body:OfferResponse):
    return call(outreach.demo_response,engine(),cid,mid,body.response)

DIST=db.ROOT/'frontend/dist'
if (DIST/'assets').exists():app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
@app.get('/',include_in_schema=False)
def home():
    if not (DIST/'index.html').exists():raise HTTPException(503,'Run npm run build in frontend, or use the Vite dev server on port 5173.')
    return FileResponse(DIST/'index.html')
