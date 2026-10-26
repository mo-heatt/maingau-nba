import json
from contextlib import asynccontextmanager
from typing import Dict, List, Literal, Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import database as db
from .ingestion import import_sources
from .service import EngineService, safe
from .replay import preview

@asynccontextmanager
async def lifespan(app):
    db.initialize();import_sources();app.state.engine=EngineService();yield

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
    return Response(m.as_bytes(),media_type='message/rfc822',headers={'Content-Disposition':f'attachment; filename="maingau-{did}.eml"'})

DIST=db.ROOT/'frontend/dist'
if (DIST/'assets').exists():app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
@app.get('/',include_in_schema=False)
def home():
    if not (DIST/'index.html').exists():raise HTTPException(503,'Run npm run build in frontend, or use the Vite dev server on port 5173.')
    return FileResponse(DIST/'index.html')
