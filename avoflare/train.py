"""Run the engine over the 15-day cohort, train the continuous deterioration-risk model with leave-one-patient-out
CV, pick the threshold, and evaluate rules / rules+ML against the fixed NEWS2 comparator (07 sec.6).
Usage: python train.py [data_dir]      Outputs: results/report.json, model/risk_model.pkl
"""
import json, os, pickle, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
import engine
from engine import PatientEngine, AlertLifecycle, load_context, comparator_priority, V, WINDOW_S

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "data"
HERE = Path(__file__).resolve().parent
OUTPUT = Path(os.environ.get("AVOFLARE_OUTPUT_DIR", str(HERE)))
RESULTS_DIR = OUTPUT / "results"
MODEL_DIR = OUTPUT / "model"
LABELS = {l["patient_id"]: l for l in json.loads((DATA / "labels.json").read_text())}
LEAD = 1800          # positive label: deteriorating now, or onset within next 30 min is NOT used (no future leak):
                     # y = 1 for windows in [onset, end]; model must detect early drift.


def extract(pid):
    d = np.load(DATA / f"{pid}.npz")
    e = PatientEngine(load_context()[pid])
    arr = {v: d[v] for v in V}
    motion, fault, activity = d["motion"], d["fault"], d["activity"]
    count = len(arr["hr"]) // WINDOW_S
    rows = None
    t_ = np.empty(count, dtype=np.int64)
    pri = np.empty(count, dtype=np.int64)
    ver = np.empty(count, dtype=bool)
    tech = np.empty(count, dtype=bool)
    comp = np.empty(count, dtype=np.int64)
    row = 0
    cmax = 0
    for t in range(len(arr["hr"])):
        o = {v: float(arr[v][t]) for v in V}
        cmax = max(cmax, comparator_priority(o))
        r = e.feed(t, o, bool(motion[t]), bool(fault[t]), bool(activity[t]))
        if r:
            if rows is None:
                rows = np.empty((count, len(r["features"])), dtype=np.float32)
            rows[row] = r["features"]
            t_[row], pri[row] = t, r["priority"]
            ver[row], tech[row], comp[row] = r["verification"], r["technical"], cmax
            row += 1
            cmax = 0
    if rows is None:
        rows = np.empty((0, 0), dtype=np.float32)
    np.savez_compressed(RESULTS_DIR / f"win_{pid}.npz", X=rows[:row], t=t_[:row],
                        pri=pri[:row], ver=ver[:row], tech=tech[:row], comp=comp[:row])
    return pid


def label(pid, t):
    y = np.zeros(len(t), int)
    for ev in LABELS[pid]["events"]:
        y[(t >= ev["onset_t"]) & (t <= ev["end_t"])] = 1
    return y


def evaluate(pid, t, pri, ver):
    """Episode-level metrics. Same lifecycle + simulated clinician closure for every system (fair comparison)."""
    lc = AlertLifecycle(auto_resolve=True)
    starts = []
    for ti, p, v in zip(t, pri, ver):
        if lc.step(int(ti), int(p), "verification" if v else "clinical") == "opened":
            starts.append((int(ti), bool(v)))
    evs = LABELS[pid]["events"]
    out = {"events": len(evs), "detected": 0, "delay_s": [], "lead_s": [], "false_clinical": 0, "verification": 0}
    matched = set()
    for ts, v in starts:
        hit = [i for i, ev in enumerate(evs) if ev["onset_t"] - 300 <= ts <= ev["recovered_t"] + 600]
        if hit:
            matched.add(hit[0])
        elif v:
            out["verification"] += 1
        else:
            out["false_clinical"] += 1
    for i, ev in enumerate(evs):      # 07 sec.6: first qualifying clinical Review/Urgent after onset
        q = (np.asarray(t) >= ev["onset_t"]) & (np.asarray(t) <= ev["recovered_t"]) & (np.asarray(pri) >= 2) & ~np.asarray(ver, bool)
        first = [int(np.asarray(t)[q][0])] if q.any() else []
        if first:
            out["detected"] += 1; out["delay_s"].append(first[0] - ev["onset_t"])
            if ev["severe_t"]: out["lead_s"].append(ev["severe_t"] - first[0])
    return out


def summarise(per):
    days = 15 * len(per)
    agg = {k: sum(p[k] for p in per.values()) for k in ("events", "detected", "false_clinical", "verification")}
    delay = [x for p in per.values() for x in p["delay_s"]]; lead = [x for p in per.values() for x in p["lead_s"]]
    return {**agg, "sensitivity": agg["detected"] / max(1, agg["events"]),
            "false_clinical_per_patient_day": round(agg["false_clinical"] / days, 3),
            "verification_per_patient_day": round(agg["verification"] / days, 3),
            "median_detection_delay_s": float(np.median(delay)) if delay else None,
            "median_lead_before_severe_s": float(np.median(lead)) if lead else None,
            "min_lead_before_severe_s": float(min(lead)) if lead else None, "per_patient": per}


def main():
    pids = sorted(LABELS)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True); MODEL_DIR.mkdir(parents=True, exist_ok=True)
    probe = PatientEngine(load_context()[pids[0]])
    probe_result = None
    for t in range(WINDOW_S):
        probe_result = probe.feed(t, {v: None for v in V})
    current_feature_count = len(probe_result["features"])
    todo = []
    for p in pids:
        cache = RESULTS_DIR / f"win_{p}.npz"
        if not cache.exists():
            todo.append(p)
            continue
        with np.load(cache) as z:
            if z["X"].ndim != 2 or z["X"].shape[1] != current_feature_count:
                todo.append(p)
    if todo:
        print(f"Rebuilding {len(todo)} feature caches for current {current_feature_count}-feature engine", flush=True)
    if todo:
        with Pool(min(10, len(todo))) as pool:
            for p in pool.imap_unordered(extract, todo): print("extracted", p, flush=True)
    W = {p: dict(np.load(RESULTS_DIR / f"win_{p}.npz")) for p in pids}
    for p in pids: W[p]["y"] = label(p, W[p]["t"])
    # leave-one-patient-out CV -> honest out-of-fold risk for every window
    params = dict(max_iter=60, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0,
                  class_weight="balanced", random_state=0)

    def fit_subset(patient_ids, seed=0):
        """Bound fit time while retaining every positive and patient-level grouping."""
        x_parts, y_parts = [], []
        for i, q in enumerate(patient_ids):
            yq = W[q]["y"]
            positives = np.flatnonzero(yq == 1)
            negatives = np.flatnonzero(yq == 0)
            rng = np.random.default_rng(seed + i)
            if len(negatives) > 10000:
                negatives = np.sort(rng.choice(negatives, 10000, replace=False))
            chosen = np.sort(np.concatenate((positives, negatives)))
            x_parts.append(W[q]["X"][chosen])
            y_parts.append(yq[chosen])
        return np.vstack(x_parts), np.concatenate(y_parts)

    for p in pids:
        tr = [q for q in pids if q != p]
        X_train, y_train = fit_subset(tr, seed=2026 + pids.index(p) * 100)
        m = HistGradientBoostingClassifier(**params).fit(X_train, y_train)
        W[p]["oof"] = m.predict_proba(W[p]["X"])[:, 1]
        print(f"LOPO fold complete: held-out {p}; fit_rows={len(y_train)}", flush=True)
    y = np.concatenate([W[p]["y"] for p in pids]); s = np.concatenate([W[p]["oof"] for p in pids])
    model_metrics = {"window_auroc_oof": round(roc_auc_score(y, s), 4), "window_auprc_oof": round(average_precision_score(y, s), 4),
                     "positives": int(y.sum()), "windows": int(len(y))}
    print(model_metrics)

    def ml_pri(p, thr):            # ML-1: risk >= thr for 3 consecutive windows raises to Review, never lowers
        hit = W[p]["oof"] >= thr
        run = np.convolve(hit, np.ones(3), "full")[: len(hit)] >= 3
        return np.where(run & (W[p]["pri"] < 2), 2, W[p]["pri"])

    # threshold sweep on OOF: maximise sensitivity, then earliest detection, subject to false burden
    sweep = []
    for thr in np.round(np.arange(0.5, 0.99, 0.04), 2):
        r = summarise({p: evaluate(p, W[p]["t"], ml_pri(p, thr), W[p]["ver"]) for p in pids})
        sweep.append({"thr": float(thr), "sens": r["sensitivity"], "fp_day": r["false_clinical_per_patient_day"],
                      "delay": r["median_detection_delay_s"]})
    rules_only = summarise({p: evaluate(p, W[p]["t"], W[p]["pri"], W[p]["ver"]) for p in pids})
    ok = [r for r in sweep if r["fp_day"] <= rules_only["false_clinical_per_patient_day"] + 1.0]
    best = min(ok or sweep, key=lambda r: (-r["sens"], r["delay"] or 1e9, r["fp_day"]))
    thr = best["thr"]
    proposed = summarise({p: evaluate(p, W[p]["t"], ml_pri(p, thr), W[p]["ver"]) for p in pids})
    comparator = summarise({p: evaluate(p, W[p]["t"], W[p]["comp"], np.zeros(len(W[p]["t"]), bool)) for p in pids})
    X_final, y_final = fit_subset(pids, seed=2026)
    final = HistGradientBoostingClassifier(**params).fit(X_final, y_final)
    model_artifact = {
        "model": final,
        "threshold": thr,
        "policy": engine.POLICY,
        "status": "experimental_synthetic_only_not_clinically_validated",
        "training_data": str(DATA.resolve()),
        "training_patients": pids,
        "feature_count": int(W[pids[0]]["X"].shape[1]),
        "fit_rows": int(len(y_final)),
        "max_negative_rows_per_patient": 10000,
        "max_iter": params["max_iter"],
        "training_method": "HistGradientBoostingClassifier; patient-grouped leave-one-patient-out diagnostics; final estimator fit on all supplied training runs",
        "threshold_method": "Exploratory threshold selected from pooled LOPO predictions summarized in report.json; threshold metrics are not an independent test",
        "clinical_deployment_allowed": False,
    }
    with (MODEL_DIR / "risk_model.pkl").open("wb") as model_file:
        pickle.dump(model_artifact, model_file)
    report = {"note": "Synthetic simulated cohort (10 patients x 15 days). Engineering evaluation, NOT clinical validation.",
              "model": model_metrics, "ml_threshold": thr, "threshold_sweep": sweep,
              "fixed_news2_comparator": comparator, "proposed_rules_only": rules_only, "proposed_rules_plus_ml": proposed}
    report["model_artifact"] = {
        "path": str((MODEL_DIR / "risk_model.pkl").resolve()),
        "status": model_artifact["status"],
        "clinical_deployment_allowed": False,
        "threshold_metrics_are_independent_test": False,
    }
    report["dataset_provenance"] = {
        "directory": str(DATA.resolve()),
        "labels_source": "offline labels.json written by the supplied engineering simulator",
        "synthetic_only": True,
        "clinical_validation": False,
    }
    (RESULTS_DIR / "report.json").write_text(json.dumps(report, indent=1, default=float))
    for k in ("fixed_news2_comparator", "proposed_rules_only", "proposed_rules_plus_ml"):
        r = report[k]
        print(f"{k:26s} sens {r['detected']}/{r['events']}  false/pt-day {r['false_clinical_per_patient_day']}"
              f"  verif/pt-day {r['verification_per_patient_day']}  delay {r['median_detection_delay_s']}s"
              f"  lead {r['median_lead_before_severe_s']}s (min {r['min_lead_before_severe_s']})")


if __name__ == "__main__":
    main()
