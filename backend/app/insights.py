"""Chart-ready observations; no interpolation of aggregate counters into a time series."""
import pandas as pd
from .ingestion import SNAPSHOT
from .service import safe


def customer_insights(engine, cid):
    profile = engine.customer(cid)
    X = engine.X
    def own(name):
        table = X[name]
        return table[table.customer_id == cid].copy()
    mobile = own('mobile_contracts')
    mobile = mobile[mobile.status == 'active']
    mobile_rows = []
    for r in mobile.to_dict(orient='records'):
        mobile_rows.append({k: r.get(k) for k in ['contract_id', 'plan', 'data_volume_gb', 'monthly_fee_eur', 'sim_count']})
        mobile_rows[-1].update(avg_data_used_gb_3m=r['avg_data_used_gb_3m'] if profile['profiling'] else None,
                               data_limit_reached_3m=r['data_limit_reached_3m'] if profile['profiling'] else None)
    months = pd.period_range(end=pd.Timestamp(SNAPSHOT), periods=6, freq='M')
    activity = {str(m): {'month': str(m), 'portal_sessions': None if not profile['profiling'] else 0, 'service_contacts': 0} for m in months}
    for name, column, key in [('service_interactions', 'created_at', 'service_contacts'), ('portal_sessions', 'session_start', 'portal_sessions')]:
        if key == 'portal_sessions' and not profile['profiling']: continue
        rows = own(name)
        dates = pd.to_datetime(rows[column], errors='coerce')
        for value in dates[dates <= SNAPSHOT]:
            month = str(value.to_period('M'))
            if month in activity: activity[month][key] += 1
    telemetry = []
    charges = []
    if profile['profiling']:
        rows = own('hems_telemetry_daily')
        if len(rows):
            rows['date'] = pd.to_datetime(rows.date)
            rows = rows[rows.date <= SNAPSHOT].sort_values('date').tail(30)
            telemetry = [{'date': str(r.date)[:10], 'consumption_kwh': r.household_consumption_kwh,
                          'solar_kwh': r.pv_generation_kwh, 'grid_import_kwh': r.grid_import_kwh} for r in rows.itertuples()]
        rows = own('charge_sessions')
        if len(rows):
            rows['date'] = pd.to_datetime(rows.started_at)
            rows = rows[rows.date <= SNAPSHOT]
            rows['date'] = rows.date.dt.strftime('%Y-%m-%d')
            charges = [{'date': day, 'energy_kwh': round(float(group.energy_kwh.sum()), 2), 'sessions': len(group)}
                       for day, group in rows.groupby('date', sort=True)][-30:]
    energy = own('energy_contracts')
    energy = energy[energy.status.isin(['active', 'cancellation_pending'])]
    contracts = [{'tariff': r.tariff, 'commodity': r.commodity, 'annual_consumption_kwh': r.annual_consumption_kwh,
                  'monthly_installment_eur': r.monthly_installment_eur, 'price_guarantee_until': r.price_guarantee_until}
                 for r in energy.itertuples()]
    return safe({'customer_id': cid, 'snapshot': SNAPSHOT.isoformat(), 'profiling': profile['profiling'],
                 'mobile': mobile_rows, 'activity': list(activity.values()), 'telemetry': telemetry,
                 'charging': charges, 'energy_contracts': contracts,
                 'notes': ['Mobile usage is a three-month aggregate, not monthly observations.',
                           'Missing daily readings are not interpolated. Source data is synthetic.']})
