import copy
import pandas as pd
import pytest
from app.insights import customer_insights
from app.ingestion import SNAPSHOT
from app import database as db
from app.service import EngineService


@pytest.fixture(scope='module')
def insight_engine():
    if not db.path().exists(): pytest.skip('Local source database required')
    return EngineService()


def test_mobile_chart_preserves_aggregate_without_inventing_months(insight_engine):
    result=customer_insights(insight_engine,'MG-100005')
    mobile=result['mobile'][0]
    assert mobile['data_volume_gb']==10
    assert mobile['avg_data_used_gb_3m']==10
    assert mobile['data_limit_reached_3m']==3
    assert 'monthly_usage' not in result
    assert [r['month'] for r in result['activity']]==['2026-04','2026-05','2026-06','2026-07','2026-08','2026-09']


def test_activity_matches_dated_observations(insight_engine):
    result=customer_insights(insight_engine,'MG-100005')
    for source,col,key in [('portal_sessions','session_start','portal_sessions'),('service_interactions','created_at','service_contacts')]:
        table=insight_engine.X[source]
        rows=table[table.customer_id=='MG-100005']
        dates=pd.to_datetime(rows[col])
        for item in result['activity']:
            assert item[key]==int(((dates.dt.strftime('%Y-%m')==item['month'])&(dates<=SNAPSHOT)).sum())


def test_no_profiling_hides_behavioural_charts(insight_engine):
    limited=copy.copy(insight_engine);limited.customer=lambda cid:{'profiling':False}
    result=customer_insights(limited,'MG-100005')
    assert result['mobile'][0]['avg_data_used_gb_3m'] is None
    assert result['mobile'][0]['data_limit_reached_3m'] is None
    assert result['telemetry']==[] and result['charging']==[]
    assert all(r['portal_sessions'] is None for r in result['activity'])


def test_daily_readings_stay_sorted_and_within_snapshot(insight_engine):
    result=customer_insights(insight_engine,'MG-100325')
    assert result['telemetry']
    assert len(result['telemetry'])<=30
    dates=[r['date'] for r in result['telemetry']]
    assert dates==sorted(dates)
    assert all(d<='2026-09-30' for d in dates)
