"""Summarise a persisted comparison batch without calling the model."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--database', default=str(ROOT / 'data/nba.sqlite'))
parser.add_argument('--output', default=str(ROOT / 'data/evaluations/ai-nba.json'))
args = parser.parse_args()
with sqlite3.connect(args.database) as conn:
    conn.row_factory = sqlite3.Row
    batch = conn.execute('SELECT * FROM ai_batches ORDER BY id DESC LIMIT 1').fetchone()
    if not batch: raise SystemExit('No comparison batch has run yet.')
    job = json.loads(batch['payload'])
    rows = []
    for ref in job['results']:
        row = conn.execute('SELECT * FROM ai_decisions WHERE id=?', (ref['id'],)).fetchone()
        value = json.loads(row['payload'])
        p = value['proposal'] or {}
        baseline = value['baseline']
        rows.append({'customer_id': row['customer_id'], 'ai_decision_id': row['id'], 'status': value['status'],
            'model': value['model'], 'prompt_version': value['prompt_version'], 'baseline_action': baseline['action'],
            'baseline_product': baseline['product_id'], 'ai_action': p.get('action'), 'ai_product': p.get('product_id'),
            'different_choice': (baseline['action'], baseline['product_id'] if baseline['action'] in ['offer','service'] else None) != (p.get('action'), p.get('product_id') if p.get('action') in ['offer','service'] else None),
            'email_saved': bool(value.get('draft_id')), 'validation_errors': value['validation_errors'],
            'error': value['error'], 'email_error': value['email_error'], 'dispatch_allowed': value['dispatch_allowed']})
summary = {'batch_id': batch['id'], 'batch_status': batch['status'], 'total': job['total'], 'completed': job['completed'],
           'status_counts': dict(Counter(r['status'] for r in rows)),
           'validated_action_counts': dict(Counter(r['ai_action'] for r in rows if r['status']=='validated')),
           'changed_validated_choices': sum(r['different_choice'] and r['status']=='validated' for r in rows),
           'email_drafts': sum(r['email_saved'] for r in rows),
           'limitation': 'Stratified synthetic sample. Validation pass measures source/policy checks, not recommendation accuracy, uplift or dispatch readiness.',
           'results': rows}
path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
print(json.dumps({k:v for k,v in summary.items() if k!='results'}, indent=2))
print('Saved:', path)
