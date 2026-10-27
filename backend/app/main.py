import json
from contextlib import asynccontextmanager
from typing import Dict, List, Literal, Optional
from pathlib import Path
from datetime import date
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from . import database as db
from .ingestion import import_sources
from .service import EngineService, safe
from .replay import preview
from . import ai_nba, assistant, outreach, portfolio, newsletter, developer, customer_import
from .insights import customer_insights
from .email_template import for_draft
from .overview import overview as overview_data
from .radar import radar as radar_data
from . import orchestration, campaigns
from .timeline import timeline as timeline_data

@asynccontextmanager
async def lifespan(app):
    db.initialize();newsletter.seed();import_sources();app.state.engine=EngineService()
    with db.connect() as c:
        c.execute("UPDATE ai_batches SET status='interrupted' WHERE status IN ('queued','running')")
    yield

app=FastAPI(title='MAINGAU NBA',version='1.0.0',lifespan=lifespan,docs_url='/api/docs',openapi_url='/api/openapi.json',redoc_url=None)

app.include_router(developer.router)

@app.exception_handler(RequestValidationError)
async def safe_developer_validation(request,exc):
    if request.url.path=='/api/developer/ai':return JSONResponse(status_code=422,content={'detail':'Submit an API key in the api_key field.'})
    return await request_validation_exception_handler(request,exc)

@app.middleware('http')
async def browser_ai_context(request,call_next):
    token=developer._active_key.set(developer.session_key(request.cookies.get(developer.COOKIE)))
    try:return await call_next(request)
    finally:developer._active_key.reset(token)


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

@app.get('/api/radar')
def radar():return radar_data(engine())

@app.get('/api/overview')
def overview():return overview_data(engine())

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
def customers(q:str='',action:Optional[str]=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=5000)):
    rows=list(engine().all().values());rows=[r for r in rows if q.lower() in (r['id']+' '+r['city']).lower() and (not action or r['decision']['action']==action)]
    rows.sort(key=lambda r:(-r['decision']['expected_gain_eur'],r['id']))
    return {'total':len(rows),'offset':offset,'limit':limit,'items':[{**{k:r[k] for k in ['id','city','since','value','decision']},'preview':{'language':r['language'],'tone':r['tone'],'profiling':r['profiling'],'products':r['products'],'open_cases':len(r['open_tickets']),'contacts_30d':r['contacts_30d'],'contact_channels':[ch['channel'] for ch in r['channels'] if ch['allowed']]}} for r in rows[offset:offset+limit]]}

class CustomerFile(BaseModel):
    filename:str=Field(max_length=200)
    content:str=Field(max_length=customer_import.MAX_BYTES)
    dry_run:bool=True

@app.get('/api/customers/import/template')
def customer_import_template(format:Literal['csv','json']='csv'):
    return Response(customer_import.template(format),media_type='text/csv' if format=='csv' else 'application/json',
                    headers={'Content-Disposition':f'attachment; filename="maingau-customer-template.{format}"'})

@app.post('/api/customers/import')
def import_customer(body:CustomerFile):
    try:result,candidate=customer_import.run(body.filename,body.content,lambda rows:EngineService(extra=rows),body.dry_run)
    except customer_import.CustomerFileError as exc:raise HTTPException(422,{'errors':exc.errors,'warnings':exc.warnings})
    # The engine builds all profiles once; the candidate already includes the stored customer, so swap it in.
    if result['stored']:app.state.engine=candidate
    return safe(result)

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

class UpgradeRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    product_id:str=Field(min_length=1,max_length=120)
    name:str=Field(min_length=1,max_length=150)
    category:str=Field(min_length=1,max_length=40)
    provider:str=Field(default='',max_length=120)
    status:str=Field(default='',max_length=40)
    details:dict=Field(default_factory=dict)

@app.post('/api/customers/{cid}/upgrade-ideas')
def upgrade_ideas(cid:str,body:UpgradeRequest):return call(portfolio.upgrade_ideas,engine(),cid,body.model_dump())

@app.get('/api/customers/{cid}/timeline')
def customer_timeline(cid:str):return call(timeline_data,engine(),cid)

@app.get('/api/customers/{cid}/insights')
def insights(cid:str):return call(customer_insights,engine(),cid)

@app.post('/api/customers/{cid}/reviews')
def review(cid:str,body:Review):return call(engine().review,cid,body.decision_id,body.status,body.note)

@app.post('/api/customers/{cid}/override')
def override(cid:str,body:Override):return call(engine().override,cid,body.offer_id,body.note)

@app.get('/api/marketing')
def marketing():return engine().marketing()

@app.post('/api/marketing/preview')
def marketing_preview(body:Settings):
    data=body.model_dump();data.pop('version');return call(orchestration.preview,engine(),data)

class Campaign(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=80)
    offer:str
    channel:str
    value_tier:List[str]=[]
    tenure:List[str]=[]
    lines:List[str]=[]
    city:List[str]=[]
    starts:Optional[date]=None
    ends:Optional[date]=None

def campaign_call(fn,*args):
    try:return fn(*args)
    except KeyError:raise HTTPException(404,'Campaign not found')
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.get('/api/campaigns/options')
def campaign_options():return campaigns.options(engine())

@app.get('/api/campaigns')
def campaign_list():return campaigns.all_campaigns(engine())

@app.post('/api/campaigns/preview')
def campaign_preview(body:Campaign):return campaign_call(campaigns.preview,engine(),body.model_dump(mode='json'))

@app.post('/api/campaigns')
def campaign_create(body:Campaign):return campaign_call(campaigns.create,engine(),body.model_dump(mode='json'))

@app.post('/api/campaigns/{cid}/launch')
def campaign_launch(cid:int):return campaign_call(campaigns.launch,engine(),cid)

@app.delete('/api/campaigns/{cid}')
def campaign_delete(cid:int):return campaign_call(campaigns.delete,cid)

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

class ChatTurn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    role:Literal['user','assistant']
    content:str=Field(min_length=1,max_length=2000)

class Chat(BaseModel):
    model_config=ConfigDict(extra='forbid')
    messages:List[ChatTurn]=Field(min_length=1,max_length=40)

@app.post('/api/assistant')
def ask_assistant(body:Chat):
    if body.messages[-1].role!='user':raise HTTPException(422,'The last message must be a question.')
    try:return assistant.answer(engine(),[m.model_dump() for m in body.messages])
    except assistant.AssistantError as exc:raise HTTPException(503,str(exc))

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
if (DIST/'fonts').exists():app.mount('/fonts',StaticFiles(directory=DIST/'fonts'),name='fonts')
if (DIST/'brand').exists():app.mount('/brand',StaticFiles(directory=DIST/'brand'),name='brand')
@app.get('/',include_in_schema=False)
def home():
    if not (DIST/'index.html').exists():raise HTTPException(503,'Run npm run build in frontend, or use the Vite dev server on port 5173.')
    return FileResponse(DIST/'index.html')
