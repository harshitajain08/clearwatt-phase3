import pytest
from app.engine import audit_bill, evaluate_binary, detect_mean_shift, cluster_consumers

def test_insufficient_history_is_not_classified_normal():
    r=audit_bill(units=300,amount=2200,period_days=30,history=[])
    assert r["status"]=="insufficient_data"
    assert r["baseline"] is None

def test_daily_normalised_historical_change():
    h=[{"period_end":f"2026-0{i}-30","period_days":30,"units":200,"amount":1500} for i in range(1,5)]
    r=audit_bill(units=300,amount=2200,period_days=30,history=h)
    assert r["baseline"]["usage_change_pct"]==50
    assert r["signals"][0]["code"]=="consumption_increase"

def test_meter_reading_mismatch_is_explained():
    r=audit_bill(units=100,amount=800,period_days=30,history=[],meter_previous=1000,meter_current=1150)
    assert r["signals"][0]["code"]=="meter_units_mismatch"

def test_meter_reading_reverse_flags_review():
    r=audit_bill(units=100,amount=800,period_days=30,history=[],meter_previous=1000,meter_current=900)
    assert r["signals"][0]["severity"]=="high"

def test_confusion_metrics_and_fpr():
    r=evaluate_binary([0,0,1,1],[0,1,1,1])
    assert r["confusion_matrix"]=={"tn":1,"fp":1,"fn":0,"tp":2}
    assert r["precision"]==pytest.approx(2/3)
    assert r["recall"]==1
    assert r["false_positive_rate"]==.5

def test_change_point():
    r=detect_mean_shift([10,11,9,10,11,40,42,39,41,40])
    assert r["change_point_index"]==5

def test_cluster_count():
    rows=[{"units_per_day":i+1,"amount_per_day":(i+1)*2} for i in range(8)]
    assert len(cluster_consumers(rows,3))==8


def test_modified_z_and_usage_change_are_independent_signals():
    history=[{"period_end":f"2026-0{i}-28","period_days":28,"units":224,"amount":1600} for i in range(1,5)]
    r=audit_bill(units=448,amount=3200,period_days=28,history=history)
    codes=[s["code"] for s in r["signals"]]
    assert "consumption_increase" in codes
    # For a constant historical series, MAD is zero and a different value has no defined robust Z.
    assert r["baseline"]["modified_z"] is None


def test_bill_algorithm_statuses_are_explicit_for_small_sample():
    from app.engine import analyse_bill_periods
    r=analyse_bill_periods([],{"period_end":"2026-11-30","period_days":30,"units":250,"amount":1800})
    assert r["sample_count"]==1
    assert all(a["status"]=="insufficient_data" for a in r["algorithms"])


def test_bill_algorithm_pipeline_runs_when_sample_requirements_met():
    from app.engine import analyse_bill_periods
    history=[{"period_end":f"2026-{i:02d}-28","period_days":28,"units":200+i*4,"amount":1400+i*28} for i in range(1,12)]
    r=analyse_bill_periods(history,{"period_end":"2026-12-28","period_days":28,"units":450,"amount":3150})
    names={a["name"]:a["status"] for a in r["algorithms"]}
    assert names["Isolation Forest"]=="ran"
    assert names["K-Means (3 groups)"]=="ran"
    assert names["Mean-shift change-point"]=="ran"


def test_synthetic_benchmark_is_deterministic_and_reports_metrics():
    from app.engine import synthetic_benchmark
    a=synthetic_benchmark();b=synthetic_benchmark()
    metrics=a["models"]["isolation_forest"]["metrics"]
    assert metrics["n"]==270
    assert metrics["accuracy"]==b["models"]["isolation_forest"]["metrics"]["accuracy"]
    assert 0<=metrics["accuracy"]<=1
    assert a["split"]["training_normal_observations"]==420
    assert "synthetic" in a["disclaimer"].lower()


def test_modified_z_score_can_fire_alongside_usage_screen():
    history=[{"period_end":f"2026-0{i}-28","period_days":28,"units":u,"amount":u*7} for i,u in enumerate([280,308,252,280,308],start=1)]
    r=audit_bill(units=840,amount=5880,period_days=28,history=history)
    codes=[s["code"] for s in r["signals"]]
    assert "consumption_increase" in codes
    assert "consumption_robust_outlier" in codes
