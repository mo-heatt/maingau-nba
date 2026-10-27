"""Ephemeral browser-scoped Hessian credentials; no credential is persisted or returned."""
import os
import re
import secrets
import time
from contextvars import ContextVar
from dataclasses import dataclass,field
from threading import Lock
from fastapi import APIRouter,HTTPException,Request,Response
from pydantic import BaseModel,ConfigDict,SecretStr
import httpx
from urllib.parse import urlsplit

COOKIE='maingau_ai_session'
TTL_SECONDS=8*60*60
_active_key=ContextVar('hessian_session_key',default=None)
_lock=Lock()
@dataclass
class Session:
    key:str=field(repr=False)
    expires:float=0
_sessions={}

def get_key():return _active_key.get() or os.getenv('HAI_API_KEY','')

def session_key(token):
    if not token:return None
    with _lock:
        entry=_sessions.get(token)
        if entry and entry.expires>time.monotonic():return entry.key
        _sessions.pop(token,None)
    return None

def status(token=None):
    personal=bool(session_key(token));server=bool(os.getenv('HAI_API_KEY'))
    return {'configured':personal or server,'session_configured':personal,'server_configured':server,
            'source':'browser_session' if personal else 'server' if server else 'not_configured',
            'model':os.getenv('NBA_AI_MODEL','vllm/Kolibri-1'),
            'base_url':os.getenv('NBA_AI_BASE_URL','https://hip-gw.hessian.ai/v1'),
            'expires_in_hours':8 if personal else None}

def require_same_origin(request):
    origin=request.headers.get('origin')
    allowed={str(request.base_url).rstrip('/'),'http://127.0.0.1:5173','http://localhost:5173'}
    public=urlsplit(os.getenv('NBA_PUBLIC_APP_URL',''))
    if public.scheme in ('http','https') and public.netloc:allowed.add(public.scheme+'://'+public.netloc)
    if origin and origin.rstrip('/') not in allowed:
        raise HTTPException(403,'Open Developer area from the same app address.')

router=APIRouter(prefix='/api/developer',tags=['Developer settings'])
class KeyInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    api_key:SecretStr

@router.get('/ai')
def connection(request:Request):return status(request.cookies.get(COOKIE))

@router.post('/ai')
async def connect(body:KeyInput,request:Request,response:Response):
    require_same_origin(request)
    raw=body.api_key.get_secret_value()
    if len(raw)>16384:raise HTTPException(400,'The API key is too long. Paste only the key value.')
    key=re.sub(r'[\s\u200b\u2060\ufeff]+','',raw)
    if not key or len(key)>8192 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise HTTPException(400,'Enter a valid API key. Spaces and line breaks are removed automatically.')
    base=os.getenv('NBA_AI_BASE_URL','https://hip-gw.hessian.ai/v1').rstrip('/')
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            check=await client.get(base+'/models',headers={'Authorization':'Bearer '+key})
        if check.status_code==401:raise HTTPException(400,'Hessian did not accept this API key (401). Copy it again from the issuer and check whether it expired or was revoked. The previous connection was kept.')
        if check.status_code==403:raise HTTPException(400,'Hessian denied access for this key (403). Check gateway and account permissions with the organiser. The previous connection was kept.')
        if check.status_code==429:raise HTTPException(429,'Hessian is limiting requests. Wait before checking again.')
        if check.status_code!=200:raise HTTPException(502,'Hessian could not verify access. The previous connection was kept.')
        ids={item.get('id') for item in check.json().get('data',[])}
        if os.getenv('NBA_AI_MODEL','vllm/Kolibri-1') not in ids:raise HTTPException(400,'This key does not list the configured model. Check access with the organiser.')
    except (httpx.HTTPError,ValueError,TypeError,AttributeError):
        raise HTTPException(502,'Could not reach Hessian to verify this key. The previous connection was kept.')
    token=secrets.token_urlsafe(32)
    with _lock:
        now=time.monotonic()
        for expired in [k for k,v in _sessions.items() if v.expires<=now]:_sessions.pop(expired,None)
        old=request.cookies.get(COOKIE)
        if len(_sessions)>=500 and old not in _sessions:raise HTTPException(503,'Too many active test sessions. Try again later.')
        _sessions.pop(old,None)
        _sessions[token]=Session(key,now+TTL_SECONDS)
    response.set_cookie(COOKIE,token,max_age=TTL_SECONDS,httponly=True,samesite='strict',secure=request.url.scheme=='https',path='/')
    return status(token)

@router.delete('/ai')
def disconnect(request:Request,response:Response):
    require_same_origin(request)
    with _lock:_sessions.pop(request.cookies.get(COOKIE),None)
    response.delete_cookie(COOKIE,path='/')
    return status()
