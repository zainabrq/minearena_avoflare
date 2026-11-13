"""Evaluate a frozen model on a new, simulator-seeded 15-day test cohort.

Labels are read only after features and model predictions are produced. This
is an engineering holdout within the same simulator family, not clinical
validation or a substitute for the user's missing wearable archive.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

import engine
from engine import AlertLifecycle, PatientEngine, V, WINDOW_S, load_context


def extract_one(args: tuple[str, str, str]) -> str:
    pid, data_dir, feature_dir = args
    d = np.load(Path(data_dir) / f"{pid}.npz")
    signals = {v: d[v] for v in V}
    motion, fault, activity = d["motion"], d["fault"], d["activity"]
    ctx = load_context()[pid]
    evaluator = PatientEngine(ctx)  # no model and no scenario/label input
    count = len(signals["hr"]) // WINDOW_S
    X = None
    times = np.empty(count, dtype=np.int64)
    priority = np.empty(count, dtype=np.int64)
    verification = np.empty(count, dtype=bool)
    technical = np.empty(count, dtype=bool)
    comp = np.empty(count, dtype=np.int64)
    comparator_max = 0
    row = 0
    for t in range(len(signals["hr"])):
        obs = {v: float(signals[v][t]) for v in V}
        comparator_max = max(comparator_max, engine.comparator_priority(obs))
        result = evaluator.feed(
            t, obs, bool(motion[t]), bool(fault[t]), bool(activity[t])
        )
        if result:
            if X is None:
                X = np.empty((count, len(result["features"])), dtype=np.float32)
            X[row] = result["features"]
            times[row] = t
            priority[row] = result["priority"]
            verification[row] = result["verification"]
            technical[row] = result["technical"]
            comp[row] = comparator_max
            comparator_max = 0
            row += 1
    if X is None:
        X = np.empty((0, 0), dtype=np.float32)
    if row != count:
        X, times, priority = X[:row], times[:row], priority[:row]
        verification, technical, comp = verification[:row], technical[:row], comp[:row]
    np.savez_compressed(
        Path(feature_dir) / f"test_{pid}.npz", X=X, t=times, pri=priority,
        ver=verification, tech=technical, comp=comp,
    )
    return pid


def label(patient_labels: dict, times: np.ndarray) -> np.ndarray:
    y = np.zeros(len(times), dtype=np.int8)
    for event in patient_labels["events"]:
        y[(times >= event["onset_t"]) & (times <= event["end_t"])] = 1
    return y


def evaluate(times: np.ndarray, priorities: np.ndarray, verification: np.ndarray,
             events: list[dict]) -> dict:
    lifecycle = AlertLifecycle(auto_resolve=True)
    starts: list[tuple[int, bool]] = []
    for t, p, v in zip(times, priorities, verification):
        if lifecycle.step(int(t), int(p), "verification" if v else "clinical") == "opened":
            starts.append((int(t), bool(v)))
    out = {"events": len(events), "detected": 0, "delay_s": [], "lead_s": [],
           "false_clinical": 0, "verification": 0}
    for t, is_verification in starts:
        matched = [i for i, event in enumerate(events)
                   if event["onset_t"] - 300 <= t <= event["recovered_t"] + 600]
        if not matched and is_verification:
            out["verification"] += 1
        elif not matched:
            out["false_clinical"] += 1
    for event in events:
        first = [t for t, is_verification in starts
                 if event["onset_t"] - 300 <= t <= event["recovered_t"] and not is_verification]
        if first:
            out["detected"] += 1
            out["delay_s"].append(first[0] - event["onset_t"])
            if event.get("severe_t") is not None:
                out["lead_s"].append(event["severe_t"] - first[0])
    return out


def summarize(per_patient: dict[str, dict]) -> dict:
    monitored_days = 15 * len(per_patient)
    agg = {key: sum(item[key] for item in per_patient.values())
           for key in ("events", "detected", "false_clinical", "verification")}
    delays = [v for item in per_patient.values() for v in item["delay_s"]]
    leads = [v for item in per_patient.values() for v in item["lead_s"]]
    return {
        **agg,
        "sensitivity": agg["detected"] / max(1, agg["events"]),
        "false_clinical_per_patient_day": round(agg["false_clinical"] / monitored_days, 3),
        "verification_per_patient_day": round(agg["verification"] / monitored_days, 3),
        "median_detection_delay_s": float(np.median(delays)) if delays else None,
        "median_lead_before_severe_s": float(np.median(leads)) if leads else None,
        "minimum_lead_before_severe_s": float(min(leads)) if leads else None,
        "per_patient": per_patient,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python evaluate_unseen.py <test_data_dir> <model_artifact.pkl> <output_dir>")
    data_dir, artifact_path, output_dir = map(Path, sys.argv[1:])
    feature_dir = output_dir / "features"
    feature_dir.mkdir(parents=True, exist_ok=True)
    patients = sorted(load_context())
    tasks = [(pid, str(data_dir), str(feature_dir)) for pid in patients]
    with Pool(min(len(tasks), 10)) as pool:
        for pid in pool.imap_unordered(extract_one, tasks):
            print(f"Unseen feature extraction complete: {pid}", flush=True)

    # The holdout labels are loaded only after the feature pass is finished.
    labels = {x["patient_id"]: x for x in json.loads((data_dir / "labels.json").read_text())}
    with artifact_path.open("rb") as file:
        artifact = pickle.load(file)
    model = artifact["model"]
    threshold = float(artifact["threshold"])

    predictions, targets = [], []
    comparator_only, rules_only, model_augmented = {}, {}, {}
    per_patient_results = {}
    for pid in patients:
        with np.load(feature_dir / f"test_{pid}.npz") as z:
            X = z["X"]
            times, pri, verification = z["t"], z["pri"], z["ver"]
            comp = z["comp"]
        y = label(labels[pid], times)
        risk = model.predict_proba(X)[:, 1]
        elevated = np.convolve(risk >= threshold, np.ones(3, dtype=np.int8), mode="full")[:len(risk)] >= 3
        combined = np.where(elevated & (pri < 2), 2, pri)
        predictions.append(risk)
        targets.append(y)
        comparator_only[pid] = evaluate(times, comp, np.zeros(len(times), dtype=bool), labels[pid]["events"])
        rules_only[pid] = evaluate(times, pri, verification, labels[pid]["events"])
        model_augmented[pid] = evaluate(times, combined, verification, labels[pid]["events"])
        per_patient_results[pid] = {
            "windows": int(len(times)), "positive_windows": int(y.sum()),
            "threshold_exceed_windows": int((risk >= threshold).sum()),
            "three_window_threshold_runs": int(elevated.sum()),
            "risk_median": round(float(np.median(risk)), 6),
            "risk_p95": round(float(np.quantile(risk, .95)), 6),
        }

    y_all, risk_all = np.concatenate(targets), np.concatenate(predictions)
    report = {
        "test_type": "unseen simulator-seed holdout; same simulator family and patient configurations",
        "simulator_seed": 2027,
        "threshold_frozen_from_training_artifact": threshold,
        "threshold_retuned_on_holdout": False,
        "training_artifact_sha256": sha256(artifact_path),
        "patients": len(patients),
        "windows": int(len(y_all)),
        "positive_windows": int(y_all.sum()),
        "window_auroc": float(roc_auc_score(y_all, risk_all)),
        "window_auprc": float(average_precision_score(y_all, risk_all)),
        "fixed_news2_comparator": summarize(comparator_only),
        "proposed_rules_only": summarize(rules_only),
        "proposed_rules_plus_model": summarize(model_augmented),
        "per_patient_model_output": per_patient_results,
        "limitations": [
            "Unseen only by random simulator seed; same simulator assumptions and patient configurations as training.",
            "Simulator labels are not observed clinical outcomes; this is not clinical validation.",
            "No threshold was tuned on the holdout. The frozen threshold came from the synthetic training run.",
            "All thresholds and clinical decision rules remain engineering prototypes.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "unseen_test_report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Unseen test report written: {path}", flush=True)
    print(json.dumps({key: report[key] for key in (
        "windows", "positive_windows", "window_auroc", "window_auprc",
        "fixed_news2_comparator", "proposed_rules_only", "proposed_rules_plus_model"
    )}, indent=2), flush=True)


if __name__ == "__main__":
    main()
