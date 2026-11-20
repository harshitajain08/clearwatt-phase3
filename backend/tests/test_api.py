from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_health_and_methodology():
    assert client.get('/api/health').status_code==200
    assert client.get('/api/methodology').status_code==200

def test_manual_audit_and_report():
    r=client.post('/api/audits/manual',json={'period_start':'2026-10-01','period_end':'2026-10-30','units':250,'amount':1800,'meter_ref':'REPORT-TEST-METER'})
    assert r.status_code==200
    assert r.json()['status'] in ('insufficient_data','review','no_signal')  # history may exist from other test runs
    report=client.get(f"/api/audits/{r.json()['id']}/report")
    assert report.status_code==200 and report.headers['content-type']=='application/pdf'

def test_meter_csv_validation_and_aggregation():
    csv='meter_id,timestamp,reading_kwh\nM1,2026-10-01T00:00:00Z,100\nM1,2026-10-01T00:15:00Z,101.2\nM1,2026-10-01T00:30:00Z,102.5\nM2,2026-10-01T00:00:00Z,200\nM2,2026-10-01T00:15:00Z,202\n'
    r=client.post('/api/meter/upload',files={'file':('meters.csv',csv,'text/csv')})
    assert r.status_code==200
    assert r.json()['meter_count']==2
    assert r.json()['valid_rows']==5

def test_wrong_file_type_rejected():
    r=client.post('/api/meter/upload',files={'file':('meters.txt','hello','text/plain')})
    assert r.status_code==415


def test_saved_bills_are_automatically_used_as_history():
    periods=[("2024-07-01","2024-07-31",180), ("2024-08-01","2024-08-31",195), ("2024-09-01","2024-09-30",190)]
    for start,end,units in periods:
        r=client.post('/api/audits/manual',json={"period_start":start,"period_end":end,"units":units,"amount":units*7,"meter_ref":"HISTORY-TEST-METER"})
        assert r.status_code==200
    final=client.post('/api/audits/manual',json={"period_start":"2024-10-01","period_end":"2024-10-31","units":340,"amount":2380,"meter_ref":"HISTORY-TEST-METER"})
    assert final.status_code==200
    assert final.json()["history_periods"] >= 3
    assert final.json()["status"] in ("review","no_signal")
    assert len(final.json()["history"]) >= 4


def test_ml_benchmark_endpoint_exposes_synthetic_metrics():
    r=client.get('/api/ml/benchmark')
    assert r.status_code==200
    data=r.json()
    assert data['models']['isolation_forest']['metrics']['n']==270
    assert data['models']['isolation_forest']['metrics']['confusion_matrix']
    assert 'synthetic' in data['disclaimer'].lower()


def test_meter_upload_returns_ml_status_for_daily_usage():
    rows=['meter_id,timestamp,reading_kwh']
    cumulative=0.0
    for day in range(1,18):
        daily=(8.0 + (day % 3)*2.0) if day!=14 else 35.0
        cumulative+=daily
        rows.append(f'M1,2026-10-{day:02d}T23:00:00Z,{cumulative:.2f}')
    csv='\n'.join(rows)
    r=client.post('/api/meter/upload',files={'file':('meter.csv',csv,'text/csv')})
    assert r.status_code==200
    meter=r.json()['meters'][0]
    assert meter['algorithm_analysis']['observations']>=12
    statuses={a['name']:a['status'] for a in meter['algorithm_analysis']['algorithms']}
    assert statuses['Isolation Forest']=='ran'
    assert statuses['K-Means (3 daily-usage groups)']=='ran'

def test_bill_metadata_persisted_and_audits_searchable():
    payload={"period_start":"2025-07-01","period_end":"2025-07-31","units":245,"amount":1712.5,"meter_ref":"CW-SEARCH-TEST-01","consumer_ref":"TEST-CONSUMER-01","discom":"UPPCL"}
    r=client.post('/api/audits/manual',json=payload)
    assert r.status_code==200
    listing=client.get('/api/audits',params={"search":"CW-SEARCH-TEST-01"})
    assert listing.status_code==200
    assert any(x['meter_ref']==payload['meter_ref'] and x['amount']==1712.5 for x in listing.json())
    summary=client.get('/api/audits/summary').json()
    assert summary['stored_records']>=1
    assert summary['audit_runs']>=1

def test_history_is_isolated_by_meter_reference():
    for i,(start,end,units) in enumerate([("2025-01-01","2025-01-31",190),("2025-02-01","2025-02-28",200),("2025-03-01","2025-03-31",210)]):
        client.post('/api/audits/manual',json={"period_start":start,"period_end":end,"units":units,"amount":units*7,"meter_ref":"ISOLATION-METER-A"})
    # Another meter's bill must not leak into the first meter's historical baseline.
    client.post('/api/audits/manual',json={"period_start":"2025-04-01","period_end":"2025-04-30","units":900,"amount":9000,"meter_ref":"ISOLATION-METER-B"})
    final=client.post('/api/audits/manual',json={"period_start":"2025-04-01","period_end":"2025-04-30","units":400,"amount":2800,"meter_ref":"ISOLATION-METER-A"})
    assert final.status_code==200
    assert final.json()['history_periods']==3
    assert all(h['units']<500 for h in final.json()['history'])
