"""Known products with provenance; a competitor quote is not a competitor contract."""
import json
import re
from . import database as db
from .service import safe


def external_records(cid):
    with db.connect() as c:rows=c.execute('SELECT * FROM external_products WHERE customer_id=? ORDER BY id',(cid,)).fetchall()
    return [{**json.loads(r['payload']),'id':r['id']} for r in rows]


def products(engine,cid):
    engine.customer(cid)
    result=[]
    def add(category,name,provider,status,source,reference,details,relationship='contract'):
        result.append(safe({'id':f'{source}:{reference}','category':category,'name':name,'provider':provider,'status':status,
            'source':source,'source_ref':str(reference),'details':details,'relationship':relationship,'external':provider!='MAINGAU'}))
    for source in ['energy_contracts','mobile_contracts','autostrom_contracts','hems_devices','shop_orders']:
        rows=engine.X[source];rows=rows[rows.customer_id==cid]
        for r in rows.to_dict(orient='records'):
            if source=='energy_contracts':
                if r['status'] not in ['active','cancellation_pending']:continue
                add(r['commodity'],r['tariff'],'MAINGAU',r['status'],source,r['contract_id'],
                    {'unit_eur_kwh':r['energy_price_eur_kwh'],'base_eur_month':r['base_price_eur_month'],
                     'annual_kwh':r['annual_consumption_kwh'],'price_guarantee_until':r['price_guarantee_until']})
            elif source=='mobile_contracts':
                if r['status']!='active':continue
                add('mobile',r['plan'],'MAINGAU',r['status'],source,r['contract_id'],{'data_gb':r['data_volume_gb'],'monthly_eur':r['monthly_fee_eur'],'sim_count':r['sim_count'],'minimum_term_end':r['min_term_end']})
            elif source=='autostrom_contracts':
                if r['status']!='active':continue
                add('charging',r['product'],'MAINGAU',r['status'],source,r['contract_id'],{'ac_eur_kwh':r['ac_price_eur_kwh'],'dc_eur_kwh':r['dc_price_eur_kwh']})
            elif source=='hems_devices':
                add('devices',r['device_type'].replace('_',' '),r['manufacturer'] or 'Manufacturer unknown',r['connection_status'],source,r['device_id'],{'last_seen_at':r['last_seen_at']},'connected_device')
            elif r['order_status'] not in ['cancelled','returned']:
                add('shop',r['product_name'],'MAINGAU',r['order_status'],source,r['order_id'],{'quantity':r['quantity'],'ordered_at':r['order_created_at']},'purchase_record')
    # Deliberately narrow extraction: the dataset explicitly says an external OFFER exists.
    table=engine.X['call_transcripts'];table=table[table.customer_id==cid]
    for r in table.to_dict(orient='records'):
        for line in r['transcript'].splitlines():
            if line.strip().startswith('Kunde:') and re.search(r'Ich habe ein Angebot von einem anderen Anbieter',line,re.I):
                add('external','Competing offer','Provider not named','offer received','call_transcripts',r['transcript_id'],
                    {'evidence':line.strip(),'date':r['call_started_at'],'limitation':'Offer only; an active external contract is not established.'},'competing_offer')
    for r in external_records(cid):
        add(r['category'],r['name'],r['provider'],'customer reported','external_product_records',r['id'],
            {'monthly_eur':r.get('monthly_eur'),'evidence':r['evidence'],'source_type':'operator-recorded customer statement'},'reported_contract')
    return {'customer_id':cid,'items':result,'notes':['Purchase records do not prove continuing ownership.','Missing provider data does not mean no external provider exists.']}


def add_external(engine,cid,payload):
    engine.customer(cid)
    with db.connect() as c:
        cur=c.execute('INSERT INTO external_products(customer_id,payload) VALUES (?,?)',(cid,json.dumps(payload,ensure_ascii=False)))
        db.audit(c,'external_product_recorded',{'record_id':cur.lastrowid,'source':'customer_reported'},cid)
    return products(engine,cid)
