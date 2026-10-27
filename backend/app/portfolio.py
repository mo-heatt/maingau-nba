"""Known products with provenance; a competitor quote is not a competitor contract."""
import json
import re
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from . import ai_nba
from . import database as db
from .service import safe


class UpgradeIdea(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=3, max_length=90)
    problem: str = Field(min_length=3, max_length=300)
    benefit: str = Field(min_length=3, max_length=300)


class UpgradeIdeas(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ideas: List[UpgradeIdea] = Field(min_length=3, max_length=3)


UPGRADE_PROMPT = (
    'You support a MAINGAU Energie customer advisor. Propose exactly three upgrade ideas for the '
    'customer product below. Each idea targets a different need, for example paying less, more '
    'capacity or data volume, or more convenience. Use only the supplied product facts and the '
    'MAINGAU catalogue entries as grounding; never invent prices, discounts, availability or dates. '
    'Write titles, problems and benefits in short factual English; keep product names in German. '
    'Do not cite evidence ids.'
)

# Deterministic fallback ideas, one per common need. Used when the AI provider is unavailable
# and as the guaranteed baseline; they never invent prices or dates.
RULE_IDEAS = {
    'electricity': [
        ('Check a smaller tariff tier', 'The household may use less energy than the current tier assumes.', 'Paying only for the capacity the household actually needs.'),
        ('Price guarantee for planning safety', 'Energy prices can change at short notice.', 'A tariff with a longer price guarantee makes the monthly budget predictable.'),
        ('Heat pump or dynamic tariff', 'If the household has a heat pump or flexible consumption, a special tariff may fit better.', 'Consumption can be moved to cheaper hours where the setup supports it.'),
    ],
    'gas': [
        ('Compare tariff tiers', 'The current tariff may not match the actual consumption.', 'Paying only for the consumption the household actually has.'),
        ('Price guarantee for planning safety', 'Gas prices can change at short notice.', 'A tariff with a longer price guarantee makes the monthly budget predictable.'),
        ('Combine with an efficiency check', 'Older heating setups often waste energy.', 'Lower consumption without changing the comfort level.'),
    ],
    'mobile': [
        ('Pay for less data', 'The booked data volume may exceed what the household actually uses.', 'A smaller tier can reduce the monthly fee without losing anything actually used.'),
        ('More data volume', 'Streaming or mobile work can push a small plan to its limit.', 'The next tariff stage avoids extra charges and throttling.'),
        ('Additional SIM for the household', 'Family members may still be on separate contracts.', 'One bundled contract with additional SIMs is easier to manage.'),
    ],
    'internet': [
        ('Check the next speed stage', 'Slow connections or many parallel devices suggest the line is too small.', 'Stable connections for every device in the household.'),
        ('Check fibre availability', 'DSL may no longer be the fastest option at the connection address.', 'Fibre, where available, handles streaming and home office easily.'),
        ('Bundle with MAINGAU energy', 'Internet and electricity come from different providers today.', 'One provider for both means one contact point and combined offers.'),
    ],
    'charging': [
        ('Home charging tariff check', 'Public charging is usually more expensive than the home wallbox.', 'Charging at home on the right tariff costs clearly less per kWh.'),
        ('Wallbox integration into HEMS', 'The wallbox may not be part of the home energy management yet.', 'Solar surplus can be prioritised for charging.'),
        ('Charging card for longer trips', 'Charging away from home needs a simple option.', 'One card or app for public charging across networks.'),
    ],
    'devices': [
        ('Connect the device to HEMS', 'A connected device alone does not optimise anything yet.', 'The home energy management can steer the device intelligently.'),
        ('Storage optimisation check', 'An existing home storage may not charge at the best times.', 'More self-used solar energy means less bought electricity.'),
        ('Smart thermostats for the heating', 'Heating without schedules wastes energy.', 'Rooms are warm when needed and save energy the rest of the time.'),
    ],
    'shop': [
        ('Smart Plug set for measurable savings', 'Standby and unnoticed consumers drive the bill up.', 'Consumption becomes visible and controllable per device.'),
        ('Balcony solar for a first step', 'The household may want to produce its own electricity without a big installation.', 'A plug-in solar set lowers the bill with a small one-off cost.'),
        ('Smart thermostats for the heating', 'Heating without schedules wastes energy.', 'Rooms are warm when needed and save energy the rest of the time.'),
    ],
}

GENERIC_IDEAS = [
    ('Check the tariff fits the usage', 'Usage may have changed since the product was chosen.', 'Paying only for what the household actually needs.'),
    ('Look for a comfort upgrade', 'The current product may miss features the household now wants.', 'More convenience with a product that matches daily routines.'),
    ('Bundle with other MAINGAU lines', 'The product may be cheaper or simpler together with other MAINGAU products.', 'One provider, one contact point, combined conditions.'),
]

CATEGORY_TO_LINE = {'electricity': 'energy', 'gas': 'energy', 'mobile': 'mobile', 'internet': 'internet',
                    'charging': 'e_mobility', 'devices': 'smart_living', 'shop': 'shop'}


def _catalogue(engine, category):
    line = CATEGORY_TO_LINE.get(category)
    rows = engine.X['product_catalog']
    rows = rows if line is None else rows[rows.business_line == line]
    return [{'product_id': r['product_id'], 'product_name': r['product_name'],
             'description': r['description']} for r in rows.to_dict(orient='records')]


def upgrade_ideas(engine, cid, product):
    """Three upgrade ideas for one known product: AI grounded in the catalogue, rule-based fallback."""
    engine.customer(cid)
    profile = engine.customer(cid)
    fallback = [{'title': t, 'problem': p, 'benefit': b} for t, p, b in RULE_IDEAS.get(product['category'], GENERIC_IDEAS)]
    result = {'customer_id': cid, 'product_id': product['product_id'], 'ideas': fallback,
              'source': 'catalogue-rules', 'model': None, 'note': None}
    try:
        material, usage = ai_nba.complete(UpgradeIdeas, UPGRADE_PROMPT, {
            'customer': {'id': cid, 'tone': profile.get('tone')},
            'product': {'name': product['name'], 'category': product['category'],
                        'provider': product.get('provider', ''), 'status': product.get('status', ''),
                        'details': product.get('details', {})},
            'maingau_catalogue': _catalogue(engine, product['category'])})
        result.update(ideas=[i.model_dump() for i in material.ideas], source='ai',
                      model=ai_nba.provider_status()['model'], usage=usage)
    except Exception as exc:  # ProviderError, validation, network — the rule ideas stay correct.
        result['note'] = 'AI unavailable, showing catalogue-based standard ideas: ' + str(exc)
    with db.connect() as c:
        db.audit(c, 'upgrade_ideas_shown', {'product_id': product['product_id'], 'source': result['source']}, cid)
    return result


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
