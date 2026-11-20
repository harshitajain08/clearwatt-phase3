from __future__ import annotations
from statistics import median
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.metrics import classification_report

METHODOLOGY = {
    "usage_spike": {"threshold_pct": 50, "minimum_history_periods": 3, "basis": "daily-normalised consumption against median of prior periods"},
    "modified_z": {"threshold": 3.5, "basis": "median absolute deviation; reported separately from the usage-change screen"},
    "isolation_forest": {"minimum_rows": 12, "contamination": 0.05, "basis": "unsupervised outlier screening; not probability or ground truth"},
    "kmeans": {"minimum_rows": 6, "default_clusters": 3, "basis": "descriptive grouping of consumption observations; not anomaly detection"},
    "change_point": {"minimum_rows": 6, "basis": "single mean-shift candidate by minimum within-segment SSE; exploratory"},
}


def robust_z(values, value):
    med = median(values)
    mad = median([abs(v - med) for v in values])
    if mad == 0:
        return 0.0 if value == med else None
    return .6745 * (value - med) / mad



def audit_bill(*, units: float, amount: float, period_days: int, history: list[dict], meter_previous: float | None = None, meter_current: float | None = None) -> dict:
    if units < 0 or amount < 0 or period_days <= 0:
        raise ValueError("Units and amount must be non-negative and billing days must be positive.")
    signals = []
    daily = units / period_days
    if meter_previous is not None and meter_current is not None:
        delta = meter_current - meter_previous
        if delta < 0:
            signals.append({"code": "meter_reading_reverse", "title": "Meter readings need verification", "severity": "high", "explanation": "The current reading is lower than the previous reading. Check whether the meter was replaced, reset or entered incorrectly.", "observed": delta, "method": "Meter-reading sequence validation"})
        elif abs(delta - units) > max(2, units * .02):
            signals.append({"code": "meter_units_mismatch", "title": "Meter difference and billed units do not match", "severity": "medium", "explanation": f"The difference between the entered meter readings is {delta:.2f} units, while the bill lists {units:.2f} units. Check multiplier, meter replacement, adjustments and reading dates.", "observed": units, "baseline": delta, "method": "Meter delta reconciliation"})
    valid = [h for h in history if h.get("period_days", 0) > 0 and h.get("units", -1) >= 0]
    valid = sorted(valid, key=lambda x: x.get("period_end", ""))[-12:]
    baseline = None
    if len(valid) < 3:
        status = "insufficient_data"
        notice = "Add at least three previous bills for a meaningful historical comparison. This check cannot label the usage as normal without enough history."
    else:
        values = [h["units"] / h["period_days"] for h in valid]
        base = median(values)
        change = None if base == 0 else (daily - base) / base * 100
        z = robust_z(values, daily)
        # Keep the percentage screen and robust statistical screen independent so one does not hide the other.
        if change is not None and change >= 50 - 1e-9:
            signals.append({"code": "consumption_increase", "title": "Your daily electricity use is higher than usual", "severity": "medium", "explanation": f"You used {daily:.2f} units per day compared with a historical median of {base:.2f} units per day. That is a {change:.1f}% increase. Seasonal conditions, visitors or appliance use may explain it.", "observed": round(daily, 3), "baseline": round(base, 3), "change_pct": round(change, 2), "method": "Daily-normalised historical median; 50% screening threshold"})
        if z is not None and abs(z) > 3.5:
            signals.append({"code": "consumption_robust_outlier", "title": "This period differs from your usual usage", "severity": "low", "explanation": f"Daily use is {daily:.2f} units. The robust modified Z-score is {z:.2f}, beyond the 3.5 screening threshold.", "observed": round(daily, 3), "baseline": round(base, 3), "modified_z": round(z, 3), "method": "Modified Z-score using median absolute deviation"})
        status = "review" if signals else "no_signal"
        notice = "An unusual pattern is a reason to review the bill, not proof that the bill is incorrect."
        baseline = {"daily_units_median": round(base, 3), "usage_change_pct": None if change is None else round(change, 2), "modified_z": None if z is None else round(z, 3), "periods": len(valid)}
    recommendations = ["Compare the meter reading on the bill with the meter display, including any meter multiplier.", "Check whether the billing period is longer or shorter than your previous bills.", "Consider seasonal appliance use, guests or changes in occupancy before treating higher usage as a billing issue."]
    if any(s["code"] == "meter_units_mismatch" for s in signals):
        recommendations.insert(0, "Ask your electricity provider to clarify the meter-reading difference and any adjustment or multiplier applied.")
    return {"status": status, "summary": "We found a pattern worth reviewing." if signals else ("We need more previous bills for a fair comparison." if status == "insufficient_data" else "No unusual consumption pattern was detected by the available checks."), "daily_units": round(daily, 3), "history_periods": len(valid), "baseline": baseline, "signals": signals, "screening_points": len(signals), "notice": notice, "recommendations": recommendations}



def analyse_bill_periods(history: list[dict], current: dict) -> dict:
    """Run methods only when their stated sample-size requirements are met."""
    observations = []
    for h in sorted(history, key=lambda x: x.get("period_end", "")):
        days = float(h.get("period_days", 0) or 0)
        units = float(h.get("units", 0) or 0)
        amount = float(h.get("amount", 0) or 0)
        if days > 0 and units >= 0 and amount >= 0:
            observations.append({"period_end": h.get("period_end", ""), "units_per_day": units / days, "amount_per_day": amount / days})
    observations.append({"period_end": current.get("period_end", ""), "units_per_day": float(current["units"]) / float(current["period_days"]), "amount_per_day": float(current["amount"]) / float(current["period_days"]), "is_current": True})
    result = {"sample_count": len(observations), "algorithms": []}
    if len(observations) >= METHODOLOGY["isolation_forest"]["minimum_rows"]:
        try:
            output = isolation_forest(observations)
            current_row = output[-1]
            result["algorithms"].append({"name": "Isolation Forest", "status": "ran", "current_result": current_row["label"], "anomaly_score": round(current_row["anomaly_score"], 5), "observations": len(observations), "note": "Unsupervised outlier screening; score is not a probability and bill-period data may be too small for stable conclusions."})
        except (ValueError, KeyError, TypeError) as exc:
            result["algorithms"].append({"name": "Isolation Forest", "status": "error", "reason": str(exc)})
    else:
        result["algorithms"].append({"name": "Isolation Forest", "status": "insufficient_data", "required": 12, "available": len(observations), "reason": "At least 12 valid bill-period observations are required; no prediction was produced."})
    feature_matrix = np.asarray([[row["units_per_day"], row["amount_per_day"]] for row in observations])
    distinct_profiles = len(np.unique(feature_matrix, axis=0))
    if len(observations) >= METHODOLOGY["kmeans"]["minimum_rows"] and distinct_profiles >= 3:
        try:
            clusters = cluster_consumers(observations, 3)
            result["algorithms"].append({"name": "K-Means (3 groups)", "status": "ran", "current_cluster": clusters[-1]["cluster"], "observations": len(observations), "note": "Descriptive grouping of bill periods for this account, not a consumer-wide profile. Cluster IDs have no inherent ranking."})
        except (ValueError, KeyError, TypeError) as exc:
            result["algorithms"].append({"name": "K-Means (3 groups)", "status": "error", "reason": str(exc)})
    else:
        result["algorithms"].append({"name": "K-Means (3 groups)", "status": "insufficient_data", "required": 6, "available": len(observations), "distinct_profiles": distinct_profiles, "reason": "At least six bill-period observations and three distinct feature profiles are required for descriptive clustering."})
    daily_values = [row["units_per_day"] for row in observations]
    if len(daily_values) >= METHODOLOGY["change_point"]["minimum_rows"]:
        try:
            cp = detect_mean_shift(daily_values, 3)
            result["algorithms"].append({"name": "Mean-shift change-point", "status": "ran", **cp, "observations": len(daily_values)})
        except (ValueError, TypeError) as exc:
            result["algorithms"].append({"name": "Mean-shift change-point", "status": "error", "reason": str(exc)})
    else:
        result["algorithms"].append({"name": "Mean-shift change-point", "status": "insufficient_data", "required": 6, "available": len(daily_values), "reason": "At least six ordered observations are required."})
    return result


def evaluate_binary(y_true: list[int], y_pred: list[int]) -> dict:
    if len(y_true) != len(y_pred) or not y_true:
        raise ValueError("Labels must be non-empty and have equal lengths.")
    if any(x not in (0, 1) for x in y_true + y_pred):
        raise ValueError("Labels must be binary (0 normal, 1 anomaly).")
    tp = sum(a == 1 and b == 1 for a, b in zip(y_true, y_pred))
    tn = sum(a == 0 and b == 0 for a, b in zip(y_true, y_pred))
    fp = sum(a == 0 and b == 1 for a, b in zip(y_true, y_pred))
    fn = sum(a == 1 and b == 0 for a, b in zip(y_true, y_pred))
    div = lambda a, b: a / b if b else None
    p = div(tp, tp + fp); r = div(tp, tp + fn); s = div(tn, tn + fp)
    f = div(2 * p * r, p + r) if p is not None and r is not None and p + r else None
    return {"n": len(y_true), "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp}, "accuracy": (tp + tn) / len(y_true), "precision": p, "recall": r, "specificity": s, "f1": f, "false_positive_rate": None if s is None else 1 - s, "warning": "Metrics apply only to this labelled dataset, not to all consumers or real-world deployment."}



def isolation_forest(rows: list[dict]) -> list[dict]:
    if len(rows) < 12:
        raise ValueError("At least 12 observations are required for this screening method.")
    x = np.asarray([[float(r["units_per_day"]), float(r["amount_per_day"])] for r in rows])
    if not np.isfinite(x).all():
        raise ValueError("All feature values must be finite numbers.")
    model = IsolationForest(contamination=.05, random_state=42)
    labels = model.fit_predict(x); scores = model.decision_function(x)
    return [{"index": i, "label": "review_candidate" if labels[i] < 0 else "no_outlier_flag", "anomaly_score": float(-scores[i])} for i in range(len(rows))]



def cluster_consumers(rows: list[dict], clusters: int = 3) -> list[dict]:
    if len(rows) < clusters or clusters < 2:
        raise ValueError("Provide at least two clusters and as many observations as clusters.")
    x = np.asarray([[float(r["units_per_day"]), float(r["amount_per_day"])] for r in rows])
    if not np.isfinite(x).all():
        raise ValueError("All feature values must be finite numbers.")
    if len(np.unique(x, axis=0)) < clusters:
        raise ValueError(f"At least {clusters} distinct feature profiles are required for clustering.")
    labels = KMeans(n_clusters=clusters, random_state=42, n_init=10).fit_predict(x)
    return [{"index": i, "cluster": int(v)} for i, v in enumerate(labels)]



def detect_mean_shift(values: list[float], min_segment: int = 3) -> dict:
    a = np.asarray(values, dtype=float)
    if len(a) < min_segment * 2:
        raise ValueError(f"At least {min_segment * 2} ordered observations are required.")
    if not np.isfinite(a).all():
        raise ValueError("All readings must be finite.")
    base_sse = float(((a - a.mean()) ** 2).sum()); best = None
    for i in range(min_segment, len(a) - min_segment + 1):
        l, r = a[:i], a[i:]
        sse = float(((l - l.mean()) ** 2).sum() + ((r - r.mean()) ** 2).sum())
        gain = (base_sse - sse) / base_sse if base_sse else 0
        if best is None or gain > best["gain"]:
            best = {"index": i, "before": float(l.mean()), "after": float(r.mean()), "gain": gain}
    return {"change_point_index": best["index"], "before_mean": best["before"], "after_mean": best["after"], "relative_shift_pct": None if best["before"] == 0 else (best["after"] - best["before"]) / abs(best["before"]) * 100, "variance_explained_by_split": best["gain"], "warning": "Exploratory candidate only; seasonal adjustment and statistical significance are not applied."}




def analyse_daily_meter(days: list[dict]) -> dict:
    """Unlabelled daily meter screening and descriptive clustering."""
    vals = np.asarray([float(d["consumption_kwh"]) for d in days], dtype=float)
    if not np.isfinite(vals).all() or (vals < 0).any():
        raise ValueError("Daily meter consumption must be finite and non-negative.")
    out = {"observations": len(days), "algorithms": []}
    if len(days) >= 12:
        x = vals.reshape(-1, 1)
        model = IsolationForest(contamination=.05, random_state=42).fit(x)
        labels = model.predict(x); scores = model.decision_function(x)
        out["algorithms"].append({"name": "Isolation Forest", "status": "ran", "review_candidate_days": [days[i]["date"] for i in range(len(days)) if labels[i] < 0], "anomaly_scores": [{"date": days[i]["date"], "score": round(float(-scores[i]), 5)} for i in range(len(days))], "note": "Unsupervised anomaly screening. Daily labels and scores are not probabilities or validated fault classifications."})
    else:
        out["algorithms"].append({"name": "Isolation Forest", "status": "insufficient_data", "required": 12, "available": len(days)})
    if len(days) >= 6 and len(np.unique(vals)) >= 3:
        labels = KMeans(n_clusters=3, random_state=42, n_init=10).fit_predict(vals.reshape(-1, 1))
        out["algorithms"].append({"name": "K-Means (3 daily-usage groups)", "status": "ran", "daily_clusters": [{"date": days[i]["date"], "cluster": int(labels[i])} for i in range(len(days))], "note": "Descriptive groups of daily consumption; cluster IDs are arbitrary."})
    else:
        out["algorithms"].append({"name": "K-Means (3 daily-usage groups)", "status": "insufficient_data", "required": 6, "available": len(days), "reason": "At least six observations and three distinct daily-usage values are required."})
    if len(days) >= 6:
        out["algorithms"].append({"name": "Mean-shift change-point", "status": "ran", **detect_mean_shift(vals.tolist(), 3)})
    else:
        out["algorithms"].append({"name": "Mean-shift change-point", "status": "insufficient_data", "required": 6, "available": len(days)})
    return out


def synthetic_benchmark(seed: int = 42) -> dict:
    """Deterministic held-out benchmark. This is synthetic and must not be presented as field validation."""
    rng = np.random.default_rng(seed)
    n_normal, n_anomaly = 600, 120
    normal_units = np.clip(rng.normal(8.5, 1.7, n_normal), 2.5, None)
    normal_amount = normal_units * rng.normal(7.2, .35, n_normal) + rng.normal(0, 3, n_normal)
    # Anomalies are a mixture of unusually high usage and atypical charge-per-unit profiles.
    anomaly_units = rng.choice([1.8, 23.0, 29.0], size=n_anomaly, p=[.25, .5, .25]) * rng.normal(1, .08, n_anomaly)
    anomaly_amount = anomaly_units * rng.choice([5.0, 11.5, 16.0], size=n_anomaly) + rng.normal(0, 5, n_anomaly)
    x_normal = np.column_stack([normal_units, normal_amount])
    x_anomaly = np.column_stack([anomaly_units, anomaly_amount])
    # Split normal samples: train IF only on the normal training partition; hold out both classes.
    permutation = rng.permutation(n_normal)
    train_idx, test_idx = permutation[:420], permutation[420:]
    x_train = x_normal[train_idx]
    x_test = np.vstack([x_normal[test_idx], x_anomaly[:90]])
    y_test = np.array([0] * len(test_idx) + [1] * 90)
    if_model = IsolationForest(contamination=.05, random_state=seed).fit(x_train)
    if_pred = (if_model.predict(x_test) == -1).astype(int)
    # Transparent baseline: a three-sigma upper limit for daily units, trained on normal training data.
    threshold = float(x_train[:, 0].mean() + 3 * x_train[:, 0].std(ddof=0))
    baseline_pred = (x_test[:, 0] > threshold).astype(int)
    return {"name": "ClearWatt synthetic anomaly benchmark v1", "dataset": "Generated synthetic daily consumption/amount observations", "seed": seed, "split": {"training_normal_observations": len(train_idx), "held_out_normal_observations": len(test_idx), "held_out_anomaly_observations": 90, "test_size": len(y_test)}, "features": ["units_per_day", "amount_per_day"], "models": {"isolation_forest": {"metrics": evaluate_binary(y_test.tolist(), if_pred.tolist()), "parameters": {"contamination": .05, "random_state": seed, "fit_data": "normal-only training partition"}}, "three_sigma_units_baseline": {"metrics": evaluate_binary(y_test.tolist(), baseline_pred.tolist()), "threshold_units_per_day": threshold}}, "disclaimer": "These are reproducible synthetic benchmark results, not field accuracy, not UPPCL validation, and not evidence that a real bill is incorrect."}
