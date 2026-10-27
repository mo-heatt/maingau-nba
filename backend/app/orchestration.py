"""Numbers for the marketing orchestration dashboard: where the value is, who it reaches, and who the rules protect.

Everything is counted from the engine's current decisions, so a rule change shows up here at once.
"""
import collections

from .engine.constants import SNAPSHOT

ACTIONABLE = ('offer', 'service')

# Why a customer gets no contact this run. Order matters: first match wins.
LEFT_ALONE = [
    ('human_review', 'Cancellation received: retention team decides'),
    ('wait', 'Contact limit reached'),
    ('service_case', 'Open service case, nothing worth fixing'),
    ('below_min', 'Best option worth less than a contact'),
    ('no_offer', 'No eligible offer: none relevant, or all blocked by rules'),
]

# Why an offer was blocked for a customer, matched on the engine's block text.
PROTECTED = [
    ('Exclusion', 'exclusion', 'Exclusion: complaint, dunning or cancellation'),
    ('Profiling consent', 'consent_profiling', 'No profiling consent: no personal marketing'),
    ('No marketing channel', 'consent_channel', 'No channel with consent'),
    ('Text is not approved', 'text', 'Text not approved for this tone'),
]


def tenure(since):
    years = (SNAPSHOT.date().toordinal() - _date(since).toordinal()) / 365.25
    return 'New (< 1 year)' if years < 1 else 'Established (1–5 years)' if years < 5 else 'Loyal (5+ years)'


def _date(iso):
    import datetime as dt
    return dt.date.fromisoformat(str(iso)[:10])


def tiers(rows):
    """Value tiers by CLV: top 20 %, middle 60 %, bottom 20 % of all customers."""
    values = sorted(r['value']['clv'] for r in rows.values())
    hi, lo = values[int(len(values) * 0.8)], values[int(len(values) * 0.2)]
    return lambda clv: 'High value (top 20 %)' if clv >= hi else 'Low value (bottom 20 %)' if clv < lo else 'Core (middle 60 %)'


def left_alone(d):
    if d['action'] in ('human_review', 'wait'):
        return d['action']
    if d['action'] != 'none':
        return None
    reason = d['reason']
    return 'service_case' if 'service case' in reason else 'below_min' if 'not worth a contact' in reason else 'no_offer'


def segments(rows):
    """Customers, actions and value per segment, for each way of cutting the base."""
    tier = tiers(rows)
    cuts = {
        'Value tier': lambda r: tier(r['value']['clv']),
        'Tenure': lambda r: tenure(r['since']),
        'Product lines': lambda r: 'Single line' if r['value']['lines'] <= 1 else 'Multi-line (2+)',
        'Tone': lambda r: 'Du' if r['decision']['tone'] == 'du' else 'Sie',
    }
    out = {}
    for name, key in cuts.items():
        groups = collections.defaultdict(list)
        for r in rows.values():
            groups[key(r)].append(r)
        out[name] = sorted((_segment(label, members) for label, members in groups.items()), key=lambda s: -s['expected_gain_eur'])
    return out


def _segment(label, members):
    acts = [r['decision'] for r in members if r['decision']['action'] in ACTIONABLE]
    top = collections.Counter(d['name'] for d in acts).most_common(1)
    return {'segment': label, 'customers': len(members), 'actions': len(acts),
            'offers': sum(d['action'] == 'offer' for d in acts), 'service_fixes': sum(d['action'] == 'service' for d in acts),
            'expected_gain_eur': round(sum(d['expected_gain_eur'] for d in acts), 2),
            'avg_clv_eur': round(sum(r['value']['clv'] for r in members) / len(members), 2),
            'top_action': top[0][0] if top else None, 'top_action_customers': top[0][1] if top else 0}


def mix(decisions, key):
    out = collections.defaultdict(lambda: {'customers': 0, 'expected_gain_eur': 0.0})
    for d in decisions:
        m = out[key(d)]; m['customers'] += 1; m['expected_gain_eur'] += d['expected_gain_eur']
    return sorted(({'key': k, 'customers': v['customers'], 'expected_gain_eur': round(v['expected_gain_eur'], 2)} for k, v in out.items()),
                  key=lambda m: -m['expected_gain_eur'])


def protected(rows):
    """Customers for whom at least one offer was blocked by a hard rule, per rule."""
    count = collections.Counter()
    for r in rows.values():
        hit = {key for c in r['candidates'] for b in c['blocked'] for prefix, key, _ in PROTECTED if b.startswith(prefix)}
        count.update(hit)
    return [{'key': key, 'label': label, 'customers': count[key]} for _, key, label in PROTECTED]


def totals(rows):
    """Compact summary that the what-if preview compares before and after."""
    ds = [r['decision'] for r in rows.values()]
    acts = [d for d in ds if d['action'] in ACTIONABLE]
    by_action = collections.Counter(d['name'] for d in acts)
    return {'expected_gain_eur': round(sum(d['expected_gain_eur'] for d in acts), 2),
            'contactable_gain_eur': round(sum(d['expected_gain_eur'] for d in acts if not d['control_group']), 2),
            'offers': sum(d['action'] == 'offer' for d in ds), 'service_fixes': sum(d['action'] == 'service' for d in ds),
            'wait': sum(d['action'] == 'wait' for d in ds), 'no_contact': sum(d['action'] not in ACTIONABLE for d in ds),
            'by_action': dict(by_action), 'channels': dict(collections.Counter(d['channel'] for d in acts)),
            'tones': dict(collections.Counter(d['tone'] for d in acts))}


def dashboard(rows):
    ds = [r['decision'] for r in rows.values()]
    acts = [d for d in ds if d['action'] in ACTIONABLE]
    reasons = collections.Counter(left_alone(d) for d in ds)
    status = collections.Counter('held_out' if d['control_group'] else d['status'] for d in acts)
    return {
        'segments': segments(rows),
        'channel_mix': mix(acts, lambda d: d['channel']),
        'tone_mix': mix(acts, lambda d: d['tone']),
        'left_alone': [{'key': k, 'label': label, 'customers': reasons[k]} for k, label in LEFT_ALONE],
        'protected': protected(rows),
        'funnel': {k: status[k] for k in ('pending', 'approved', 'rejected', 'stale', 'held_out')},
        'contactable_gain_eur': round(sum(d['expected_gain_eur'] for d in acts if not d['control_group']), 2),
        'approved_gain_eur': round(sum(d['expected_gain_eur'] for d in acts if d['status'] == 'approved' and not d['control_group']), 2),
        # Content approval: which live decisions use each template and tone.
        'template_use': _template_use(acts),
    }


def _template_use(acts):
    out = collections.defaultdict(lambda: collections.Counter())
    for d in acts:
        if d['product_id']:
            out[d['product_id']][d['tone']] += 1
    return {k: dict(v) for k, v in out.items()}


def preview(engine, values):
    before = totals(engine.all())
    after = totals(engine.preview_settings(values))
    return {'before': before, 'after': after}
