import datetime as dt
import json
import math
import openpyxl
import pandas as pd
from . import database as db

SNAPSHOT=dt.datetime(2026,9,30,23,59)

def serial(value):
    if isinstance(value,(dt.datetime,dt.date)):return value.isoformat()
    if isinstance(value,float) and not math.isfinite(value):return None
    return value

def import_sources():
    workbook=db.ROOT/'data/maingau_nba_mockdata.xlsx'
    if not workbook.exists():raise RuntimeError('Put maingau_nba_mockdata.xlsx in data/ before starting the server.')
    wb=openpyxl.load_workbook(workbook,read_only=True,data_only=True)
    with db.connect() as c:
        if c.execute('SELECT 1 FROM source_records LIMIT 1').fetchone():return
        for sheet in wb:
            values=iter(sheet.values);headers=next(values,None)
            if not headers:continue
            if sheet.title in ['README','clv_method']:
                c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(sheet.title,json.dumps([list(r) for r in values],default=str)));continue
            records=[]
            for row in values:
                record={k:serial(v) for k,v in zip(headers,row) if k}
                records.append((sheet.title,record.get('customer_id'),json.dumps(record,ensure_ascii=False)))
            c.executemany('INSERT INTO source_records(source,customer_id,payload) VALUES (?,?,?)',records)
        db.audit(c,'dataset_imported',{'workbook':workbook.name,'snapshot':SNAPSHOT.isoformat()})
    wb.close()

def load_tables(extra=()):
    """extra: (source, record) pairs not yet stored, so an upload can be scored before it is committed."""
    grouped={}
    with db.connect() as c:
        for r in c.execute('SELECT source,payload FROM source_records ORDER BY id'):
            grouped.setdefault(r['source'],[]).append(json.loads(r['payload']))
    for source,record in extra:grouped.setdefault(source,[]).append(record)
    tables={name:pd.DataFrame(rows) for name,rows in grouped.items()}
    # Observations must have been available by the source snapshot.
    cs=tables['charge_sessions'];tables['charge_sessions']=cs[pd.to_datetime(cs.cdr_received_at)<=SNAPSHOT].copy()
    si=tables['service_interactions'].copy();future=pd.to_datetime(si.resolved_at)>SNAPSHOT
    si.loc[future,'status']='open'
    for col in ['resolved_at','resolution_code','csat_1to5','goodwill_eur']:si.loc[future,col]=None
    tables['service_interactions']=si
    return tables,{'late_charge_records_excluded':len(cs)-len(tables['charge_sessions']),'future_resolutions_masked':int(future.sum())}
