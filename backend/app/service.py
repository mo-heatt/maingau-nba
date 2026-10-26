import copy
import hashlib
import json
import math
from collections import Counter
from threading import RLock
import pandas as pd
from . import database as db
from .ingestion import load_tables, SNAPSHOT
from .engine.state import build_state
from .engine.scoring import params, acceptance_model, score_customer
from .engine.arbitration import arbitrate
from .engine.content import message
from .engine.templates import TEMPLATES


def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,set):return sorted(safe(v) for v in value)
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    if hasattr(value,'item'):return safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def control(cid):return int(hashlib.sha256(cid.encode()).hexdigest(),16)%1000<100


class EngineService:
    def __init__(self):
        self.lock=RLock();self.X,self.quality=load_tables();self.P=params(self.X);self.A=acceptance_model(self.X)
        self.catalog=self.X['product_catalog'].set_index('product_id');self.state=build_state(self.X)
        comp=self.X['service_interactions'];comp=comp[(comp.category=='complaint')&(comp.status=='closed')]
        self.fcr=float(comp.first_contact_resolution.mean());self.cache={}

    def settings(self):
        with db.connect() as c:r=c.execute('SELECT version,payload FROM settings WHERE id=1').fetchone()
        return {**json.loads(r['payload']),'version':r['version']}

    def update_settings(self,values,version):
        # Revision check prevents one marketer silently overwriting another's changes.
        with self.lock,db.connect() as c:
            row=c.execute('SELECT version,payload FROM settings WHERE id=1').fetchone()
            if row['version']!=version:raise ValueError('Settings changed. Reload before saving.')
            payload=json.loads(row['payload']);payload.update(values)
            self.validate_settings(payload)
            c.execute('UPDATE settings SET version=version+1,payload=? WHERE id=1',(json.dumps(payload),));db.audit(c,'settings_updated',payload)
            self.cache.clear()
        return self.settings()

    def validate_settings(self,p):
        from .engine.constants import CHANNELS
        if set(p['offers_off'])-set(self.catalog.index):raise ValueError('Unknown offer')
        if set(p['priorities'])-set(self.catalog.index):raise ValueError('Unknown offer priority')
        if set(p['channels_off'])-set(CHANNELS):raise ValueError('Unknown channel')
        if set(p['content_approvals'])-set(TEMPLATES):raise ValueError('Unknown template')

    def evaluate(self,cid,settings=None,override=None):
        if cid not in self.state:raise KeyError(cid)
        settings=settings or self.settings();s=dict(self.state[cid])
        if settings['tone_mode']=='sie' or s['consent'].get('profiling_analytics',{}).get('status')!='granted':
            s['tone']='sie';s['tone_reason']='Formal default / marketing tone policy'
        sc=score_customer(s,self.X,self.P,self.A,self.catalog,self.fcr,settings)
        decision=arbitrate(s,sc,settings)
        if override:
            candidate=next((r for r in sc['candidates'] if r['offer']==override['offer_id']),None)
            # Overrides obey all normal gates, including contact cap, content and disabled offers.
            if not candidate or candidate['blocked'] or candidate['dclv']<=settings['min_dclv_eur'] or decision['action'] in ['wait','human_review']:
                raise ValueError('Override is no longer eligible under current rules')
            if sc['service_case'] and candidate['type']!='service':raise ValueError('Sales are blocked during a service case')
            decision={'action':'offer','pick':candidate,'title':candidate['name'],'reason':'Changed by marketing: '+override['note'],'log':['Override passed server rules']}
        pick=decision.get('pick');kind='service' if pick and pick['type']=='service' and decision['action']=='offer' else decision['action']
        identity=hashlib.sha256(json.dumps(safe({'customer':cid,'state':s,'settings':settings,'decision':decision}),sort_keys=True).encode()).hexdigest()[:24]
        result={'id':identity,'action':kind,'product_id':pick['offer'] if pick else None,'name':decision['title'],'channel':pick['channel'] if pick else None,'tone':s['tone'],'p_accept':pick['p'] if pick else None,'expected_gain_eur':pick['dclv'] if pick and kind in ['offer','service'] else 0,'reason':decision['reason'],'log':decision['log'],'control_group':control(cid),'message':message(s,decision) if kind in ['offer','service'] else None,'status':'held_out' if control(cid) else 'pending','overridden':bool(override)}
        return safe({'id':cid,'city':s['city'],'since':s['customer_since'],'household_size':s['household_size'],'language':s['language'],'portal_account':s['portal_account'],'app_installed':s['app_installed'],'value':{**s['value'],'clv':sc['clv_now'],'churn':sc['churn_now']},'products':s['products'],'signals':[{'key':k,'value':v['value'],'class':v['class'],'evidence':s['evidence'].get(k,[])} for k,v in s['signals'].items() if sc['profiling'] or v['class']!='behavioural'],'consent':s['consent'],'profiling':sc['profiling'],'tone':s['tone'],'tone_reason':s['tone_reason'],'tone_sample':s['tone_sample'] if sc['profiling'] else None,'contacts_30d':s['contacts_30d'],'open_tickets':s['open_tickets'],'tickets':s['recent_tickets'],'history':s['legacy_actions'],'channels':sc['channels'],'candidates':sc['candidates'],'decision':result,'data_quality':self.quality})

    def all(self):
        with self.lock:
            settings=self.settings();version=settings['version']
            with db.connect() as c:
                overrides={r['customer_id']:dict(r) for r in c.execute('SELECT * FROM overrides')}
                reviews={}
                for r in c.execute('SELECT * FROM reviews ORDER BY id'):reviews[r['customer_id']]=dict(r)
            key=(version,json.dumps(overrides,sort_keys=True))
            if key not in self.cache:
                rows={}
                for cid in self.state:
                    try:rows[cid]=self.evaluate(cid,settings,overrides.get(cid))
                    except ValueError:
                        rows[cid]=self.evaluate(cid,settings);rows[cid]['decision']['log'].append('Saved override expired: current rules no longer allow it')
                self.cache={key:rows}
            result=copy.deepcopy(self.cache[key])
            for cid,row in result.items():
                r=reviews.get(cid)
                if r and not row['decision']['control_group']:
                    row['decision']['status']=r['status'] if r['decision_id']==row['decision']['id'] else 'stale'
            return result

    def customer(self,cid):
        rows=self.all()
        if cid not in rows:raise KeyError(cid)
        return rows[cid]

    def review(self,cid,decision_id,status,note=''):
        with self.lock:
            row=self.customer(cid);d=row['decision']
            if d['id']!=decision_id:raise ValueError('Decision changed. Review the current recommendation.')
            if d['control_group']:raise ValueError('Control-group actions are held out')
            if d['action'] not in ['offer','service']:raise ValueError('No actionable recommendation')
            with db.connect() as c:
                c.execute('INSERT INTO reviews(customer_id,decision_id,status,note) VALUES (?,?,?,?)',(cid,decision_id,status,note));db.audit(c,'decision_'+status,{'decision_id':decision_id,'note':note},cid)
        return self.customer(cid)['decision']

    def override(self,cid,offer_id,note):
        with self.lock:
            if offer_id:self.evaluate(cid,override={'offer_id':offer_id,'note':note})
            with db.connect() as c:
                if offer_id:c.execute('INSERT OR REPLACE INTO overrides(customer_id,offer_id,note) VALUES (?,?,?)',(cid,offer_id,note))
                else:c.execute('DELETE FROM overrides WHERE customer_id=?',(cid,))
                db.audit(c,'override_updated',{'offer_id':offer_id,'note':note},cid)
            self.cache.clear()
        return self.customer(cid)

    def marketing(self):
        rows=list(self.all().values());actions=[r for r in rows if r['decision']['action'] in ['offer','service']]
        aggregate={}
        for r in actions:
            d=r['decision'];a=aggregate.setdefault(d['product_id'],{'product_id':d['product_id'],'name':d['name'],'customers':0,'expected_gain_eur':0});a['customers']+=1;a['expected_gain_eur']+=d['expected_gain_eur']
        return safe({'customers':len(rows),'expected_gain_eur':round(sum(r['decision']['expected_gain_eur'] for r in actions),2),'offers':sum(r['decision']['action']=='offer' for r in rows),'service_fixes':sum(r['decision']['action']=='service' for r in rows),'held_out':sum(r['decision']['control_group'] and r['decision']['action'] in ['offer','service'] for r in rows),'approved':sum(r['decision']['status']=='approved' for r in rows),'no_contact':sum(r['decision']['action'] not in ['offer','service'] for r in rows),'queue':sorted([r for r in actions if not r['decision']['control_group']],key=lambda r:r['decision']['expected_gain_eur'],reverse=True)[:25],'top_actions':sorted(aggregate.values(),key=lambda a:a['expected_gain_eur'],reverse=True),'quality':self.quality,'acceptance':self.A})
