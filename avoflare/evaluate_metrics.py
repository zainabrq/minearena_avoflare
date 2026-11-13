"""Evidence-based metrics for every model, recomputed from results/win_*.npz + data/labels.json.
Window = 10 s decision; positive = labelled deterioration [onset, end]. 95% CI = patient-cluster bootstrap (1000x).
Run: python evaluate_metrics.py   -> results/evaluation_metrics.json"""
import json
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

HERE = Path(__file__).resolve().parent
LAB = {l["patient_id"]: l for l in json.loads((HERE / "data/labels.json").read_text())}
PIDS = sorted(LAB)
THR = json.loads((HERE / "results/report.json").read_text())["ml_threshold"]
rng = np.random.default_rng(0)

W = {p: dict(np.load(HERE / f"results/win_{p}.npz")) for p in PIDS}
for p in PIDS:
    y = np.zeros(len(W[p]["t"]), int)
    for ev in LAB[p]["events"]:
        y[(W[p]["t"] >= ev["onset_t"]) & (W[p]["t"] <= ev["end_t"])] = 1
    W[p]["y"] = y
params = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, class_weight="balanced", random_state=0)
for p in PIDS:                                                   # leave-one-patient-out, identical to train.py
    tr = [q for q in PIDS if q != p]
    m = HistGradientBoostingClassifier(**params).fit(np.vstack([W[q]["X"] for q in tr]), np.concatenate([W[q]["y"] for q in tr]))
    W[p]["s"] = m.predict_proba(W[p]["X"])[:, 1]
    hit = W[p]["s"] >= THR
    run = np.convolve(hit, np.ones(3), "full")[: len(hit)] >= 3
    W[p]["pred"] = {"Fixed NEWS2": W[p]["comp"] >= 2,
                    "Avoflare rules": (W[p]["pri"] >= 2) & ~W[p]["ver"],
                    "Risk model alone (ML-1)": run,
                    "Avoflare rules + risk model": ((W[p]["pri"] >= 2) & ~W[p]["ver"]) | run}


def conf(ps, name):
    y = np.concatenate([W[p]["y"] for p in ps]); x = np.concatenate([W[p]["pred"][name] for p in ps])
    tp, fp = int((x & (y == 1)).sum()), int((x & (y == 0)).sum()); fn, tn = int((~x & (y == 1)).sum()), int((~x & (y == 0)).sum())
    return tp, fp, fn, tn


def stats(tp, fp, fn, tn):
    se, sp = tp / max(1, tp + fn), tn / max(1, tn + fp); ppv = tp / max(1, tp + fp)
    return {"sensitivity": se, "specificity": sp, "ppv": ppv, "npv": tn / max(1, tn + fn),
            "f1": 2 * ppv * se / max(1e-9, ppv + se), "accuracy": (tp + tn) / (tp + fp + fn + tn),
            "balanced_accuracy": (se + sp) / 2}


def boot(fn):
    vals = []
    for _ in range(1000):
        ps = list(rng.choice(PIDS, len(PIDS)))
        if sum(W[p]["y"].sum() for p in ps) == 0: continue
        vals.append(fn(ps))
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)]


out = {"definition": "10 s windows; positive = simulated deterioration interval; 95% CI patient-cluster bootstrap",
       "windows": int(sum(len(W[p]["y"]) for p in PIDS)), "positive_windows": int(sum(W[p]["y"].sum() for p in PIDS)),
       "classifiers": {}}
for name in W[PIDS[0]]["pred"]:
    c = conf(PIDS, name); s = stats(*c)
    out["classifiers"][name] = {"confusion": dict(zip(("TP", "FP", "FN", "TN"), c)),
                                **{k: round(v, 4) for k, v in s.items()},
                                "sensitivity_ci": boot(lambda ps: stats(*conf(ps, name))["sensitivity"]),
                                "specificity_ci": boot(lambda ps: stats(*conf(ps, name))["specificity"]),
                                "ppv_ci": boot(lambda ps: stats(*conf(ps, name))["ppv"])}
y = np.concatenate([W[p]["y"] for p in PIDS]); s = np.concatenate([W[p]["s"] for p in PIDS])
bins = np.minimum((s * 10).astype(int), 9)
ece = sum(abs(s[bins == b].mean() - y[bins == b].mean()) * (bins == b).mean() for b in range(10) if (bins == b).any())
cat = lambda ps, f: f(np.concatenate([W[p]["y"] for p in ps]), np.concatenate([W[p]["s"] for p in ps]))
out["risk_model"] = {"auroc": round(roc_auc_score(y, s), 4), "auroc_ci": boot(lambda ps: cat(ps, roc_auc_score)),
                     "auprc": round(average_precision_score(y, s), 4), "auprc_ci": boot(lambda ps: cat(ps, average_precision_score)),
                     "prevalence": round(float(y.mean()), 5), "brier": round(brier_score_loss(y, s), 5),
                     "expected_calibration_error": round(float(ece), 4), "threshold": THR,
                     "per_patient_auroc": {p: round(roc_auc_score(W[p]["y"], W[p]["s"]), 4) for p in PIDS if W[p]["y"].any()},
                     "note": "class_weight=balanced => scores are not calibrated probabilities (see ECE); used as a ranking score"}
(HERE / "results/evaluation_metrics.json").write_text(json.dumps(out, indent=1))
for k, v in out["classifiers"].items():
    print(f"{k:28s} Se {v['sensitivity']:.3f} {v['sensitivity_ci']}  Sp {v['specificity']:.4f} {v['specificity_ci']}  PPV {v['ppv']:.3f} {v['ppv_ci']}  F1 {v['f1']:.3f}  {v['confusion']}")
print({k: v for k, v in out["risk_model"].items() if k != "note"})
