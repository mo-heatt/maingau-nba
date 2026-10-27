import pytest
from app import lifecycle, campaigns, ai_nba
from test_outreach import engine, provider


def test_metrics_are_deterministic_and_explain_stages(engine):
    a = lifecycle.metrics(engine)
    b = lifecycle.metrics(engine)
    assert a == b
    assert a
    for p in a:
        assert p['stage'] in ('growing', 'mature', 'aging', 'legacy', 'dormant')
        assert isinstance(p['reasons'], list) and p['reasons']
        assert p['adopters'] >= 0
    names = [p['product'] for p in a]
    assert 'StromAktiv' in names and any(n.startswith('Mobil') for n in names)


def test_mobile_misfit_counts_real_contracts(engine):
    rows = engine.X['mobile_contracts']
    rows = rows[rows.status.isin(['active', 'cancellation_pending'])]
    tight = int(((rows.avg_data_used_gb_3m >= .8 * rows.data_volume_gb) | (rows.data_limit_reached_3m > 0)).sum())
    wide = int((rows.avg_data_used_gb_3m <= .3 * rows.data_volume_gb).sum())
    mobile = {p['product']: p for p in lifecycle.metrics(engine) if p['source'] == 'mobile_contracts'}
    assert sum(p['undersized'] for p in mobile.values()) == tight
    assert sum(p['oversized'] for p in mobile.values()) == wide


def test_opportunities_reuse_engine_euros(engine):
    """Portfolio gains are summed from the same per-customer candidates the app shows."""
    ops = lifecycle.opportunities(engine)
    state = engine.all()
    for o in ops:
        assert o['expected_gain_eur'] >= 0
        assert o['contactable'] <= o['adopters']
        manual = 0.0
        for cid in (cid for cid, r in state.items() if any(p['name'] == o['product'] and p['status'] in ('active', 'cancellation_pending') for p in r['products'])):
            best = max((c for c in state[cid]['candidates']
                        if c['line'] == o['line'] and c['offer'] != 'P-SV-01' and c['dclv'] > 0 and not c['blocked']),
                       key=lambda c: c['dclv'], default=None)
            if best:
                manual += best['dclv']
        assert o['expected_gain_eur'] == pytest.approx(round(manual, 2))


def test_guarantee_cliff_only_counts_the_next_120_days(engine):
    from app.ingestion import SNAPSHOT
    from datetime import date
    rows = engine.X['energy_contracts']
    rows = rows[rows.status.isin(['active', 'cancellation_pending'])]
    expected = sum(1 for v in rows.price_guarantee_until.dropna()
                   if 0 <= (date.fromisoformat(str(v)[:10]) - SNAPSHOT.date()).days <= 120)
    total = sum(c['contracts'] for c in lifecycle.cliffs(engine))
    assert total == expected


def test_campaign_product_filter_targets_only_holders(engine):
    opts = campaigns.options(engine)
    assert opts['product']
    tariff = opts['product'][0]
    holders = {cid for cid, r in engine.all().items() if any(p['name'] == tariff for p in r['products'])}
    a = campaigns.audience(engine, {'offer': 'P-EN-02', 'channel': 'email', 'product': [tariff]})
    assert a['targeted'] == len(holders)


def test_ai_brief_is_grounded_in_computed_figures(engine, provider):
    result = lifecycle.brief(engine, refresh=True)
    assert result['source'] in ('ai', 'catalogue-rules')
    b = result['brief']
    assert b['headline'] and b['recommendations']
    gains = {o['expected_gain_eur'] for o in lifecycle.opportunities(engine)}
    names = {p['product'] for p in lifecycle.metrics(engine)}
    for r in b['recommendations']:
        assert r['product'] in names
        assert r['expected_gain_eur'] == 0 or round(r['expected_gain_eur'], 2) in gains
        assert r['action'] in ('refresh', 'migrate', 'bundle', 'monitor')


def test_brief_falls_back_when_ai_fails(engine, provider, monkeypatch):
    def broken(*a, **k):raise ai_nba.ProviderError('offline')
    monkeypatch.setattr(ai_nba, 'complete', broken)
    result = lifecycle.brief(engine, refresh=True)
    assert result['source'] == 'catalogue-rules' and 'unavailable' in (result['note'] or '')
    assert result['brief']['recommendations']
