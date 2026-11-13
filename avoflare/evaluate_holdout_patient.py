"""Run one frozen-model holdout on a new-seed synthetic patient trajectory.

This narrow engineering test uses a three-day window containing P003's single
simulated event. It adapts the current 44-feature engine output to the trained
model's legacy 36-feature prefix. It is not a clinical validation test.
"""
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

import engine
from engine import AlertLifecycle, PatientEngine, V, WINDOW_S, load_context


def episode_metrics(times, priorities, verification, events):
    lifecycle = AlertLifecycle(auto_resolve=True)
    starts = []
    for t, priority, is_verification in zip(times, priorities, verification):
        if lifecycle.step(int(t), int(priority), "verification" if is_verification else "clinical") == "opened":
            starts.append((int(t), bool(is_verification)))
    false_clinical = 0
    verification_count = 0
    for t, is_verification in starts:
        matched = any(event["onset_t"] - 300 <= t <= event["recovered_t"] + 600 for event in events)
        if not matched and is_verification:
            verification_count += 1
        elif not matched:
            false_clinical += 1
    detected = 0
    delays, leads = [], []
    for event in events:
        qualifying = [t for t, is_verification in starts if not is_verification
                      and event["onset_t"] - 300 <= t <= event["recovered_t"]]
        if qualifying:
            detected += 1
            delays.append(qualifying[0] - event["onset_t"])
            if event.get("severe_t") is not None:
                leads.append(event["severe_t"] - qualifying[0])
    return {
        "events": len(events), "detected": detected,
        "sensitivity": detected / max(1, len(events)),
        "false_clinical_episodes": false_clinical,
        "verification_episodes": verification_count,
        "median_detection_delay_s": float(np.median(delays)) if delays else None,
        "median_lead_before_severe_s": float(np.median(leads)) if leads else None,
        "minimum_lead_before_severe_s": int(min(leads)) if leads else None,
    }


def main():
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python evaluate_holdout_patient.py <test_data_dir> <model.pkl> <report.json>")
    data_dir, model_path, report_path = map(Path, sys.argv[1:])
    pid = "P003"
    ctx = load_context()[pid]
    data = np.load(data_dir / f"{pid}.npz")
    labels_all = json.loads((data_dir / "labels.json").read_text())
    labels = next(item for item in labels_all if item["patient_id"] == pid)
    event = labels["events"][0]
    source_start = max(0, int(event["onset_t"]) - 1800)
    pre_event_warmup = int(event["onset_t"]) - source_start
    signals = {v: data[v] for v in V}
    motion, fault, activity = data["motion"], data["fault"], data["activity"]
    source_end = min(len(signals["hr"]), int(event["recovered_t"]) + 600)
    max_seconds = source_end - source_start
    test_events = [{key: (int(value) - source_start if key.endswith("_t") and value is not None else value)
                    for key, value in event.items()}]
    with model_path.open("rb") as file:
        artifact = pickle.load(file)
    model = artifact["model"]
    threshold = float(artifact["threshold"])
    model_features = int(artifact["feature_count"])

    engine_model = PatientEngine(ctx)
    expected_windows = max_seconds // WINDOW_S
    X = np.empty((expected_windows, model_features), dtype=np.float32)
    times = np.empty(expected_windows, dtype=np.int64)
    rules = np.empty(expected_windows, dtype=np.int64)
    verification = np.empty(expected_windows, dtype=bool)
    comparator = np.empty(expected_windows, dtype=np.int64)
    comparator_max = 0
    row = 0
    start = time.monotonic()
    for t in range(max_seconds):
        source_t = source_start + t
        observation = {v: float(signals[v][source_t]) for v in V}
        comparator_max = max(comparator_max, engine.comparator_priority(observation))
        result = engine_model.feed(t, observation, bool(motion[source_t]),
                                   bool(fault[source_t]), bool(activity[source_t]))
        if result:
            features = np.asarray(result["features"], dtype=np.float32)
            if len(features) < model_features:
                raise RuntimeError(f"Engine emitted {len(features)} features; model requires {model_features}")
            X[row] = features[:model_features]
            times[row] = t
            rules[row] = result["priority"]
            verification[row] = result["verification"]
            comparator[row] = comparator_max
            comparator_max = 0
            row += 1
        if t and t % 86400 == 0:
            print(f"Processed {t // 86400} of {max_seconds // 86400} holdout days", flush=True)
    X, times, rules = X[:row], times[:row], rules[:row]
    verification, comparator = verification[:row], comparator[:row]
    risk = model.predict_proba(X)[:, 1]

    y = np.zeros(len(times), dtype=np.int8)
    for event in test_events:
        y[(times >= event["onset_t"]) & (times <= event["end_t"])] = 1
    elevated = np.convolve(risk >= threshold, np.ones(3, dtype=np.int8), mode="full")[:len(risk)] >= 3
    rules_plus_model = np.where(elevated & (rules < 2), 2, rules)

    if len(np.unique(y)) != 2:
        auc = ap = None
    else:
        auc = float(roc_auc_score(y, risk))
        ap = float(average_precision_score(y, risk))
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    report = {
        "test_type": "new simulator seed, same P003 profile and simulator family",
        "patient_id": pid,
        "simulator_seed": 2027,
        "simulated_duration_seconds": max_seconds,
        "source_time_start_seconds": source_start,
        "source_time_end_seconds": source_end,
        "pre_event_warmup_seconds": pre_event_warmup,
        "test_event_count_in_window": len(test_events),
        "threshold_frozen_from_model_artifact": threshold,
        "threshold_retuned_on_holdout": False,
        "model_sha256": digest,
        "windows": int(row),
        "positive_windows": int(y.sum()),
        "feature_adapter": {
            "current_engine_feature_count": len(result["features"]) if result else None,
            "model_feature_count": model_features,
            "method": "Pass the first 36 legacy features; exclude eight appended slow-drift features.",
            "reason": "The saved model was trained on 36-feature caches; the current engine emits 44 features.",
        },
        "window_metrics": {"auroc": auc, "auprc": ap, "mean_risk": float(np.mean(risk)),
                           "risk_p95": float(np.quantile(risk, 0.95)),
                           "windows_at_or_above_threshold": int((risk >= threshold).sum()),
                           "three_consecutive_window_triggers": int(elevated.sum())},
        "fixed_comparator": episode_metrics(times, comparator, np.zeros(row, dtype=bool), test_events),
        "rules_only": episode_metrics(times, rules, verification, test_events),
        "rules_plus_model": episode_metrics(times, rules_plus_model, verification, test_events),
        "elapsed_feature_extraction_seconds": round(time.monotonic() - start, 2),
        "limitations": [
            "Only one patient configuration and one generated event were evaluated.",
            "This is a random-seed holdout, not a held-out patient population.",
            "The model was trained on simulator-derived labels, not wearable clinical outcomes.",
            "The 36-feature adapter excludes eight features added to the current 44-feature engine; this result does not validate direct runtime integration.",
            "Not clinical validation; do not use for patient care or production alerting.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "window_metrics", "fixed_comparator", "rules_only", "rules_plus_model", "elapsed_feature_extraction_seconds"
    )}, indent=2), flush=True)
    print(f"Saved holdout report: {report_path}", flush=True)


if __name__ == "__main__":
    main()
