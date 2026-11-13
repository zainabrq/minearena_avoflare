"""How the models behaved: per-event timelines, feature importance, ROC/PR, calibration, threshold trade-off,
false-alert analysis, twin forecast error. Leave-one-patient-out (every score is from a model that never saw that patient).
Run: python evaluate_model.py  -> results/model_evaluation.json"""
import json
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve, precision_recall_curve

HERE = Path(__file__).resolve().parent
LAB = {l["patient_id"]: l for l in json.loads((HERE / "data/labels.json").read_text())}
PIDS = sorted(LAB); REP = json.loads((HERE / "results/report.json").read_text()); THR = REP["ml_threshold"]
V = ("hr", "rr", "spo2", "temp")
FEAT = [f"{v}.{k}" for v in V for k in ("value", "delta_vs_baseline", "robust_z", "slope_1min", "slope_5min", "news2_component", "abnormal_s_in_30s", "valid_fraction")] + \
       ["exertion_context", "news2_subtotal", "scored_components", "candidate_deviations"] + [f"{v}.{k}" for v in V for k in ("median5min_minus_baseline", "median5min_change_vs_30min_ago")]
PARAMS = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, class_weight="balanced", random_state=0)

W = {p: dict(np.load(HERE / f"results/win_{p}.npz")) for p in PIDS}
for p in PIDS:
    y = np.zeros(len(W[p]["t"]), int)
    for ev in LAB[p]["events"]: y[(W[p]["t"] >= ev["onset_t"]) & (W[p]["t"] <= ev["end_t"])] = 1
    W[p]["y"] = y
cache = HERE / "results/oof_scores.npz"
if cache.exists():
    oof = dict(np.load(cache))
else:
    oof = {}
    for p in PIDS:
        tr = [q for q in PIDS if q != p]
        m = HistGradientBoostingClassifier(**PARAMS).fit(np.vstack([W[q]["X"] for q in tr]), np.concatenate([W[q]["y"] for q in tr]))
        oof[p] = m.predict_proba(W[p]["X"])[:, 1].astype(np.float32); print("oof", p, flush=True)
    np.savez_compressed(cache, **oof)
for p in PIDS: W[p]["s"] = oof[p]
y = np.concatenate([W[p]["y"] for p in PIDS]); s = np.concatenate([W[p]["s"] for p in PIDS])
out = {"threshold": THR, "windows": int(len(y)), "positives": int(y.sum())}

# discrimination curves (downsampled points for plotting)
fpr, tpr, _ = roc_curve(y, s); prec, rec, _ = precision_recall_curve(y, s)
pick = lambda a, n=120: np.unique(np.linspace(0, len(a) - 1, n).astype(int))
out["roc"] = {"auroc": round(roc_auc_score(y, s), 4), "fpr": fpr[pick(fpr)].round(4).tolist(), "tpr": tpr[pick(tpr)].round(4).tolist()}
out["pr"] = {"auprc": round(average_precision_score(y, s), 4), "prevalence": round(float(y.mean()), 5), "recall": rec[pick(rec)].round(4).tolist(), "precision": prec[pick(prec)].round(4).tolist()}
out["per_patient"] = {p: {"auroc": round(roc_auc_score(W[p]["y"], W[p]["s"]), 4) if W[p]["y"].any() else None,
                          "auprc": round(average_precision_score(W[p]["y"], W[p]["s"]), 4) if W[p]["y"].any() else None,
                          "scenario": LAB[p]["scenario"], "max_score_outside_events": round(float(W[p]["s"][W[p]["y"] == 0].max()), 3),
                          "windows_above_threshold_outside_events": int(((W[p]["s"] >= THR) & (W[p]["y"] == 0)).sum())} for p in PIDS}

# calibration (balanced class weights => ranking score; report observed frequency per bin honestly)
bins = np.linspace(0, 1, 11); idx = np.clip(np.digitize(s, bins) - 1, 0, 9)
out["calibration"] = [{"bin": f"{bins[i]:.1f}-{bins[i+1]:.1f}", "n": int((idx == i).sum()), "mean_score": round(float(s[idx == i].mean()), 3) if (idx == i).any() else None,
                       "observed_rate": round(float(y[idx == i].mean()), 4) if (idx == i).any() else None} for i in range(10)]

# per-event timeline: onset, first alert of each system, severe endpoint; risk trajectory around event
def first(t, mask, lo, hi):
    q = mask & (t >= lo) & (t <= hi); return int(t[q][0]) if q.any() else None
events = []
for p in PIDS:
    t, pri, ver, comp, sc = W[p]["t"], W[p]["pri"], W[p]["ver"], W[p]["comp"], W[p]["s"]
    run = np.convolve(sc >= THR, np.ones(3), "full")[: len(sc)] >= 3
    for ev in LAB[p]["events"]:
        o, sv, rcv = ev["onset_t"], ev["severe_t"], ev["recovered_t"]
        rel = lambda x: None if x is None else x - o
        f_c, f_r, f_m = first(t, comp >= 2, o, rcv), first(t, (pri >= 2) & ~ver, o, rcv), first(t, run, o, rcv)
        f_comb = min([x for x in (f_r, f_m) if x is not None], default=None)
        win = (t >= o - 1800) & (t <= min(rcv, o + 3 * 3600))
        tt, ss = t[win], sc[win]; step = max(1, len(tt) // 160)
        events.append({"patient": p, "scenario": LAB[p]["scenario"], "severe_after_onset_s": rel(sv), "recovered_after_onset_s": rel(rcv),
                       "first_alert_after_onset_s": {"fixed_news2": rel(f_c), "rules": rel(f_r), "risk_model_ML1": rel(f_m), "rules_plus_model": rel(f_comb)},
                       "lead_before_severe_s": None if sv is None or f_comb is None else sv - f_comb,
                       "model_first_vs_rules_s": None if f_m is None or f_r is None else f_r - f_m,
                       "trajectory": {"t": (tt[::step] - o).tolist(), "score": ss[::step].round(3).tolist(),
                                      "priority": pri[win][::step].tolist()}})
out["events"] = events

# threshold trade-off (from the executed sweep in train.py)
out["threshold_sweep"] = REP["threshold_sweep"]

# false-alert analysis from the executed episode evaluation
pp_r, pp_c = REP["proposed_rules_plus_ml"]["per_patient"], REP["fixed_news2_comparator"]["per_patient"]
out["false_alerts"] = {p: {"avoflare_per_day": round(pp_r[p]["false_clinical"] / 15, 2), "news2_per_day": round(pp_c[p]["false_clinical"] / 15, 2),
                           "verification_per_day": round(pp_r[p]["verification"] / 15, 2)} for p in PIDS}
ml_added = sum(1 for p in PIDS for v in (REP["proposed_rules_plus_ml"]["per_patient"][p]["false_clinical"] - REP["proposed_rules_only"]["per_patient"][p]["false_clinical"],) if v > 0)
out["false_alert_sources"] = {"rules_only_per_day": REP["proposed_rules_only"]["false_clinical_per_patient_day"],
                              "rules_plus_model_per_day": REP["proposed_rules_plus_ml"]["false_clinical_per_patient_day"],
                              "added_by_model_per_day": round(REP["proposed_rules_plus_ml"]["false_clinical_per_patient_day"] - REP["proposed_rules_only"]["false_clinical_per_patient_day"], 3),
                              "patients_where_model_added_false_alerts": ml_added}

# feature importance: permutation on the full-data model, balanced sample (all positives + 30k negatives)
rng = np.random.default_rng(0)
X = np.vstack([W[p]["X"] for p in PIDS]); pos = np.where(y == 1)[0]; neg = rng.choice(np.where(y == 0)[0], 30000, replace=False)
sel = np.r_[pos, neg]
full = HistGradientBoostingClassifier(**PARAMS).fit(X, y)
pi = permutation_importance(full, X[sel], y[sel], scoring="average_precision", n_repeats=3, random_state=0, n_jobs=4)
order = np.argsort(-pi.importances_mean)
out["feature_importance"] = [{"feature": FEAT[i], "drop_in_auprc": round(float(pi.importances_mean[i]), 4), "sd": round(float(pi.importances_std[i]), 4)} for i in order[:15]]
out["feature_groups"] = {g: round(float(sum(pi.importances_mean[i] for i, f in enumerate(FEAT) if f.startswith(g))), 4) for g in ("hr.", "rr.", "spo2.", "temp.")}
out["feature_groups"]["drift_5_30min"] = round(float(sum(pi.importances_mean[i] for i, f in enumerate(FEAT) if "median5min" in f)), 4)

# twin
tw = json.loads((HERE / "results/twin_report.json").read_text())
out["twin"] = {p: tw["results"][p] for p in ("P008", "P009", "P010")}; out["twin_params"] = tw["params"]
(HERE / "results/model_evaluation.json").write_text(json.dumps(out, indent=1, default=float))
for e in events: print(e["patient"], e["scenario"], e["first_alert_after_onset_s"], "severe", e["severe_after_onset_s"], "lead", e["lead_before_severe_s"])
print("top features", [(f["feature"], f["drop_in_auprc"]) for f in out["feature_importance"][:8]]); print(out["feature_groups"]); print(out["false_alert_sources"])
