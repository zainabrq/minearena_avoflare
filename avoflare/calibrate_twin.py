"""Calibrate the twin ensemble's uncertainty band (L7 uncertainty engine).
Ensemble spread alone under-covers. On TRAINING patients (P001-P007) find, per vital and horizon step, the multiplier m so
that mean +/- m*(sd + floor) contains 95% of outcomes; store it in model/twin.pt. Coverage is then re-measured on the
held-out patients P008-P010 (never used for training or calibration) and written to results/twin_report.json.
Run: python calibrate_twin.py"""
import json
from pathlib import Path
import numpy as np
import torch
import twin as TW
from engine import load_context

HERE = Path(__file__).resolve().parent
FLOOR = 0.05                                                    # normalised units
C = load_context(); ens = TW.load(); STEPS = TW.HOR["30min"]


def predict(p, idx):
    x, b, a = TW.frames(p)
    w = TW.make_windows(x, b, a, TW.ctx_vec(C[p]), idx, STEPS)
    T = {k: torch.tensor(v) for k, v in w.items() if k != "I"}
    with torch.no_grad():
        P = torch.stack([m.rollout(T["z0"], T["tr"], T["act"], T["ctx"], STEPS)[0] for m in ens.members])
    return P.mean(0).numpy(), P.std(0).numpy() + FLOOR, w["Y"]


rng = np.random.default_rng(1)
ratios = []
for p in ["P001", "P002", "P003", "P004", "P005", "P006", "P007"]:
    n = len(TW.frames(p)[0]); mu, s, y = predict(p, sorted(rng.integers(300, n - 130, 1500).tolist()))
    ratios.append(np.abs(y - mu) / s)
R = np.concatenate(ratios)                                      # windows x steps x 4
mult = np.nanquantile(R, 0.95, axis=0)                          # steps x 4
mult = np.maximum.accumulate(mult, axis=0)                      # monotone in horizon
ck = torch.load(HERE / "model/twin.pt", weights_only=False); ck["cal"] = {"mult": mult.astype(np.float32), "floor": FLOOR}
torch.save(ck, HERE / "model/twin.pt")

rep = json.loads((HERE / "results/twin_report.json").read_text())
labels = {l["patient_id"]: l for l in json.loads((HERE / "data/labels.json").read_text())}
for p in ["P008", "P009", "P010"]:
    n = len(TW.frames(p)[0])
    sets = {"all": list(range(240, n - 130, 20)),
            "deterioration": [i for e in labels[p]["events"] for i in range(e["onset_t"] // 15, e["recovered_t"] // 15, 2)]}
    for sub, idx in sets.items():
        if not idx or not rep["results"][p].get(sub): continue
        mu, s, y = predict(p, idx)
        for h, k in TW.HOR.items():
            ok = np.isfinite(y[:, k - 1]); inside = np.abs(y[:, k - 1] - mu[:, k - 1]) <= mult[k - 1] * s[:, k - 1]
            rep["results"][p][sub][h]["coverage_95_calibrated"] = dict(zip(TW.V, [round(float((inside & ok)[:, i].sum() / ok[:, i].sum()), 3) for i in range(4)]))
rep["calibration"] = {"method": "per-vital, per-step 95% quantile of |error|/(ensemble sd + floor) on training patients", "patients": "P001-P007", "floor": FLOOR}
(HERE / "results/twin_report.json").write_text(json.dumps(rep, indent=1))
for p in ["P008", "P009", "P010"]:
    print(p, {h: rep["results"][p]["all"][h]["coverage_95_calibrated"] for h in TW.HOR})
