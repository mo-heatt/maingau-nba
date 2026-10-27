"""Campaigns: one offer, one channel, one target group, checked against the same rules as the engine.

A campaign never sends anything. Creating one saves a draft; launching it records the approval.
Tracking results are SIMULATED from each customer's chance of yes and are labelled as such,
because the demo has no delivery. The simulation is seeded per campaign, so numbers stay stable.
"""
import hashlib
import json
from datetime import date

from . import database as db
from .engine.constants import CHANNELS
from .orchestration import tenure, tiers

# How many of the people sent a message see it, per channel. Assumptions for the simulation only.
SEEN_RATE = {'newsletter_email': 0.35, 'email': 0.45, 'sms': 0.9, 'app_push': 0.6, 'portal_popup': 0.7, 'outbound_call': 0.55}
# The control group still buys sometimes without a contact; share of the treated chance of yes.
CONTROL_SHARE = 0.4

FILTERS = ('value_tier', 'tenure', 'lines', 'city', 'product')
LIST_FILTERS = {'product'}  # a customer can hold several; any match counts
REASONS = {
    'control': 'Held back as control group',
    'not_relevant': 'Already has it, not relevant or switched off',
    'exclusion': 'Open complaint, dunning or cancellation',
    'profiling': 'No profiling consent',
    'channel': 'No consent or no access on this channel',
    'limit': 'Contact limit reached',
}


def _lines(r):
    return 'Single line' if r['value']['lines'] <= 1 else 'Multi-line (2+)'


def held_tariffs(engine):
    """Sellable plan/tariff names customers actually hold, for the campaign product filter."""
    from .lifecycle import _groups
    return sorted({g['name'] for g in _groups(engine)})


def options(engine):
    rows = engine.all()
    tier = tiers(rows)
    pick = lambda key: sorted({key(r) for r in rows.values()})
    return {
        'offers': [{'id': pid, 'name': name} for pid, name in engine.catalog['product_name'].items() if pid != 'P-SV-01'],
        'channels': [{'id': k, 'name': v[2]} for k, v in CHANNELS.items()],
        'value_tier': pick(lambda r: tier(r['value']['clv'])),
        'tenure': pick(lambda r: tenure(r['since'])),
        'lines': pick(_lines),
        'city': pick(lambda r: r['city']),
        'product': held_tariffs(engine),
    }


def _why_blocked(texts):
    t = ' '.join(texts).lower()
    return 'exclusion' if 'exclusion' in t else 'profiling' if 'profiling' in t else 'channel'


def audience(engine, spec):
    """Who the campaign reaches, who it may contact, and why everyone else is left out."""
    rows = engine.all()
    tier = tiers(rows)
    key = {'value_tier': lambda r: tier(r['value']['clv']), 'tenure': lambda r: tenure(r['since']), 'lines': _lines,
           'city': lambda r: r['city'], 'product': lambda r: [p['name'] for p in r['products']]}
    cap = engine.settings()['contact_cap_30d']

    def excluded(r):
        for f in FILTERS:
            wanted = spec.get(f)
            if not wanted:
                continue
            held = key[f](r)
            hit = bool(set(held) & set(wanted)) if f in LIST_FILTERS else held in wanted
            if not hit:
                return True
        return False

    targeted, contactable, left_out = [], [], {k: 0 for k in REASONS}
    for r in rows.values():
        if excluded(r):
            continue
        targeted.append(r['id'])
        option = next((o for o in r['candidates'] if o['offer'] == spec['offer']), None)
        reach = next((c for c in r['channels'] if c['channel'] == spec['channel']), None)
        reason = ('control' if r['decision']['control_group'] else
                  'not_relevant' if option is None else
                  _why_blocked(option['blocked']) if option['blocked'] else
                  'channel' if not (reach and reach['allowed']) or spec['channel'] in engine.settings()['channels_off'] else
                  'limit' if r['contacts_30d'] >= cap else None)
        if reason:
            left_out[reason] += 1
            if reason == 'control' and option and not option['blocked']:
                contactable.append({'id': r['id'], 'p': option['p'], 'dclv': option['dclv'], 'control': True})
            continue
        fit = next((c for c in option['per_channel'] if c['channel'] == spec['channel']), option)
        contactable.append({'id': r['id'], 'p': fit['p'], 'dclv': fit['dclv'], 'gain_if_yes': option['clv_accept'] - option['clv_reject'], 'control': False})
    treated = [c for c in contactable if not c['control']]
    return {
        'total': len(rows), 'targeted': len(targeted), 'contactable': len(treated),
        'control': sum(1 for c in contactable if c['control']),
        'left_out': [{'reason': k, 'label': REASONS[k], 'customers': v} for k, v in left_out.items() if v],
        'expected_gain_eur': round(sum(c['dclv'] for c in treated), 2),
        'expected_yes': round(sum(c['p'] for c in treated), 1),
        '_members': contactable,
    }


def _roll(campaign_id, cid, step):
    """A stable number in [0, 1) per campaign, customer and step."""
    h = hashlib.sha256(f'{campaign_id}:{cid}:{step}'.encode()).digest()
    return int.from_bytes(h[:8], 'big') / 2 ** 64


def tracking(campaign_id, channel, members):
    """Simulated funnel: sent, seen, said yes; plus the control group for the uplift."""
    seen_rate = SEEN_RATE.get(channel, 0.5)
    sent = seen = yes = control = control_yes = 0
    value = 0.0
    for m in members:
        if m['control']:
            control += 1
            control_yes += _roll(campaign_id, m['id'], 'control') < m['p'] * CONTROL_SHARE
            continue
        sent += 1
        if _roll(campaign_id, m['id'], 'seen') < seen_rate:
            seen += 1
            if _roll(campaign_id, m['id'], 'yes') < min(1.0, m['p'] / seen_rate):
                yes += 1
                value += m['gain_if_yes']
    rate = yes / sent if sent else None
    control_rate = control_yes / control if control else None
    return {
        'simulated': True, 'sent': sent, 'seen': seen, 'yes': yes, 'control': control, 'control_yes': control_yes,
        'yes_rate': rate, 'control_rate': control_rate,
        'uplift': None if rate is None or control_rate is None else rate - control_rate,
        'value_won_eur': round(value, 2),
    }


def _public(engine, row):
    spec = json.loads(row['payload'])
    a = audience(engine, spec)
    members = a.pop('_members')
    out = {'id': row['id'], 'status': row['status'], 'created_at': row['created_at'], 'launched_at': row['launched_at'], **spec, 'audience': a}
    out['tracking'] = tracking(row['id'], spec['channel'], members) if row['status'] == 'running' else None
    return out


def validate(engine, spec):
    if spec['offer'] not in engine.catalog.index or spec['offer'] == 'P-SV-01':
        raise ValueError('Choose an offer from the catalogue.')
    if spec['channel'] not in CHANNELS:
        raise ValueError('Choose a marketing channel.')
    if spec.get('ends') and spec.get('starts') and date.fromisoformat(spec['ends']) < date.fromisoformat(spec['starts']):
        raise ValueError('The end date is before the start date.')
    allowed = options(engine)
    for f in FILTERS:
        if set(spec.get(f) or []) - set(allowed[f]):
            raise ValueError('Unknown target group value.')


def preview(engine, spec):
    validate(engine, spec)
    a = audience(engine, spec)
    a.pop('_members')
    return a


def all_campaigns(engine):
    with db.connect() as c:
        rows = c.execute('SELECT * FROM campaigns ORDER BY id DESC').fetchall()
    return {'items': [_public(engine, r) for r in rows]}


def create(engine, spec):
    validate(engine, spec)
    with db.connect() as c:
        cid = c.execute("INSERT INTO campaigns(status,payload) VALUES ('draft',?)", (json.dumps(spec, ensure_ascii=False),)).lastrowid
        db.audit(c, 'campaign_created', {'campaign_id': cid, **spec})
        row = c.execute('SELECT * FROM campaigns WHERE id=?', (cid,)).fetchone()
    return _public(engine, row)


def launch(engine, cid):
    with db.connect() as c:
        row = c.execute('SELECT * FROM campaigns WHERE id=?', (cid,)).fetchone()
        if row is None:
            raise KeyError(cid)
        if row['status'] != 'draft':
            raise ValueError('Only a draft campaign can be launched.')
        c.execute("UPDATE campaigns SET status='running',launched_at=CURRENT_TIMESTAMP WHERE id=?", (cid,))
        db.audit(c, 'campaign_launched', {'campaign_id': cid, 'delivery': 'disabled', 'tracking': 'simulated'})
        row = c.execute('SELECT * FROM campaigns WHERE id=?', (cid,)).fetchone()
    return _public(engine, row)


def delete(cid):
    with db.connect() as c:
        row = c.execute('SELECT status FROM campaigns WHERE id=?', (cid,)).fetchone()
        if row is None:
            raise KeyError(cid)
        if row['status'] != 'draft':
            raise ValueError('Only a draft campaign can be deleted.')
        c.execute('DELETE FROM campaigns WHERE id=?', (cid,))
        db.audit(c, 'campaign_deleted', {'campaign_id': cid})
    return {'ok': True}
