import copy
import json
from collections import Counter
from . import database as db
from .engine.events import apply_event
from .engine.scoring import score_customer
from .engine.arbitration import arbitrate


def preview(engine):
    path=db.ROOT/'data/event_stream_2026-10-01.jsonl'
    if not path.exists():return {'available':False,'changes':[]}
    events=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    seen=set();duplicates=0;states={};rows=[];unhandled=Counter();settings=engine.settings()
    for event in sorted(events,key=lambda e:e['ingested_at']):
        if event['event_id'] in seen:duplicates+=1;continue
        seen.add(event['event_id']);cid=event['customer_id']
        if cid not in engine.state:continue
        s=states.setdefault(cid,copy.deepcopy(engine.state[cid]))
        def decide():return arbitrate(s,score_customer(s,engine.X,engine.P,engine.A,engine.catalog,engine.fcr,settings),settings)
        before=decide();note=apply_event(s,event,engine.P)
        if note is None:unhandled[event['event_type']]+=1;continue
        after=decide();key=lambda d:(d['action'],(d.get('pick') or {}).get('offer'),(d.get('pick') or {}).get('channel'))
        rows.append({'event_id':event['event_id'],'customer_id':cid,'type':event['event_type'],'occurred_at':event['occurred_at'],'ingested_at':event['ingested_at'],'note':note,'before':before['title'],'after':after['title'],'changed':key(before)!=key(after)})
    return {'available':True,'mode':'dry_run','source_events':len(events),'duplicates_skipped':duplicates,'handled':len(rows),'changed':sum(r['changed'] for r in rows),'unhandled_types':dict(unhandled),'changes':rows,'note':'Preview only. Current customer state is not changed; unhandled event types are listed explicitly.'}
