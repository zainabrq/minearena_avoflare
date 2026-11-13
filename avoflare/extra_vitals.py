"""Blood pressure + heart-rate variability (monitoring vitals, shown on the dashboard; they do not drive alerts).

Scores
- Systolic BP: NEWS2 (RCP 2017/2022) component bands  <=90:3, 91-100:2, 101-110:1, 111-219:0, >=220:3.
  Flag (personal baseline): score 3 always; score 2 only with a >= 15 mmHg drop from the patient's baseline.
- Shock index HR/SBP: >=1.0 -> 2, >=0.9 -> 1 (widely used bedside marker; prototype bands).
- HRV RMSSD (ms): NOT a published early-warning score. Prototype: drop vs personal baseline >=50% -> 2,
  >=30% -> 1; without a baseline RMSSD <10 ms -> 2, <15 ms -> 1.
Simulation (simulator side only): cuffless watch BP + 5-min RMSSD every 300 s, coupled to the simulated HR,
activity and scenario. Baselines are engineering assumptions (KB has no BP history).
Run: python extra_vitals.py   -> data/P*_bp_hrv.npz + results/bp_hrv_report.json
"""
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
STEP = 300                                                     # one BP/HRV reading per 5 min
DROPS_BP = {"sudden_cardiovascular", "complex_cardiac", "simulated_fever_deterioration", "heart_failure_pattern"}


def sbp_score(s):
    if s is None: return None
    s = int(np.floor(s + 0.5))
    return 3 if s <= 90 else 2 if s <= 100 else 1 if s <= 110 else 0 if s <= 219 else 3


def shock_score(hr, sbp):
    if hr is None or not sbp: return None
    si = hr / sbp
    return 2 if si >= 1.0 else 1 if si >= 0.9 else 0


def hrv_score(rmssd, baseline=None):
    if rmssd is None: return None
    if baseline:
        drop = 1 - rmssd / baseline
        return 2 if drop >= 0.5 else 1 if drop >= 0.3 else 0
    return 2 if rmssd < 10 else 1 if rmssd < 15 else 0


def assess(sbp, dbp, rmssd, hr, base):
    """base = {'sbp':..., 'rmssd':...} personal baselines (or None while calibrating)."""
    b = base or {}
    sc = sbp_score(sbp); dlt = None if sbp is None or not b.get("sbp") else sbp - b["sbp"]
    # personal BP baseline: score 3 (SBP <= 90 or >= 220) always flags; score 2 flags only with a >= 15 mmHg drop vs baseline
    flag = None if sc is None else bool(sc == 3 or (sc == 2 and (dlt is None or dlt <= -15)))
    return {"sbp": sbp, "dbp": dbp, "sbp_score": sc, "sbp_flag": flag,
            "sbp_delta": None if sbp is None or not b.get("sbp") else round(sbp - b["sbp"], 1),
            "shock_index": None if hr is None or not sbp else round(hr / sbp, 2), "shock_score": shock_score(hr, sbp),
            "rmssd": rmssd, "rmssd_baseline": b.get("rmssd"), "hrv_score": hrv_score(rmssd, b.get("rmssd")),
            "status": "monitoring_only"}


def baseline(sbp, rmssd, act):
    """Median of the first 12 h of at-rest readings (144 readings)."""
    m = ~act[:144] & ~np.isnan(sbp[:144])
    return {"sbp": float(np.median(sbp[:144][m])), "rmssd": float(np.median(rmssd[:144][m & ~np.isnan(rmssd[:144])]))}


def generate():
    cfg = json.loads((ROOT / "02_patient_data/patient_physiological_configuration_v1_1.json").read_text())
    kb = {p["patient_id"]: p for p in json.loads((ROOT / "02_patient_data/patient_kb_v1.json").read_text())["patients"]}
    for i, p in enumerate(cfg["patients"]):
        pid = p["patient_id"]; rng = np.random.default_rng(7000 + i)
        d = dict(np.load(DATA / f"{pid}.npz"))
        n = len(d["hr"]) // STEP
        hr = np.array([np.nanmedian(d["hr"][k * STEP:(k + 1) * STEP]) for k in range(n)])
        act = np.array([d["activity"][k * STEP:(k + 1) * STEP].mean() > 0.3 for k in range(n)])
        htn = any("hypertension" in c["label"].lower() for c in kb[pid]["conditions"])
        age = kb[pid]["age_at_discharge"]
        sbp0, rm0, hr0 = (140 if htn else 120) + 0.2 * (age - 50), max(12, 55 - 0.5 * age), p["initial_vitals"]["hr"]
        hod = (np.arange(n) * STEP % 86400) / 3600
        dip = -0.08 * sbp0 * (np.cos((hod - 3) / 24 * 2 * np.pi) + 1) / 2          # nocturnal dip
        dh = np.nan_to_num(hr - hr0)
        k = 0.9 if p["scenario"]["id"] in DROPS_BP else 0.1
        sbp = sbp0 + dip + np.where(act, 0.6 * dh, -k * np.clip(dh, 0, None)) + rng.normal(0, 5, n)
        dbp = 0.62 * sbp + rng.normal(0, 3, n)
        rmssd = rm0 * np.exp(-np.clip(dh, -10, None) / 18) * rng.lognormal(0, 0.12, n)
        miss = rng.random(n) < 0.05                                                    # failed watch readings
        sbp[miss] = dbp[miss] = np.nan; rmssd[rng.random(n) < 0.05] = np.nan
        np.savez_compressed(DATA / f"{pid}_bp_hrv.npz", t=np.arange(n) * STEP + STEP - 1, sbp=sbp.round(0),
                            dbp=dbp.round(0), rmssd=rmssd.round(1), hr=hr, activity=act)


def evaluate():
    """Offline test: does each score fire during labelled deterioration, and how often outside it?"""
    labels = {l["patient_id"]: l for l in json.loads((DATA / "labels.json").read_text())}
    out, tot = {}, {"sbp": [0, 0, 0], "shock": [0, 0, 0], "hrv": [0, 0, 0]}   # [events flagged, events, false flags]
    for pid, lab in sorted(labels.items()):
        z = dict(np.load(DATA / f"{pid}_bp_hrv.npz")); t = z["t"]
        b = baseline(z["sbp"], z["rmssd"], z["activity"])
        nz = lambda x: None if np.isnan(x) else float(x)
        rows = [assess(nz(z["sbp"][k]), nz(z["dbp"][k]), nz(z["rmssd"][k]), nz(z["hr"][k]), b) for k in range(len(t))]
        inside = np.zeros(len(t), bool)
        for ev in lab["events"]:
            inside |= (t >= ev["onset_t"]) & (t <= ev["recovered_t"])
        res = {"baseline": {k: round(v, 1) for k, v in b.items()}}
        for name, key in (("sbp", "sbp_flag"), ("shock", "shock_score"), ("hrv", "hrv_score")):
            flag = np.array([bool(r[key]) if key == "sbp_flag" else (r[key] or 0) >= 2 for r in rows]) & ~z["activity"]
            hit = bool((flag & inside).any()); fp = int((flag & ~inside).sum())
            res[name] = {"event_flagged": hit if lab["events"] else None, "false_flags_per_day": round(fp / 15, 2),
                         "max_score_in_event": max([int(r[key] or 0) for r, i in zip(rows, inside) if i], default=None)}
            tot[name][0] += hit; tot[name][1] += bool(lab["events"]); tot[name][2] += fp
        out[pid] = res
    summary = {k: {"events_flagged": f"{v[0]}/{v[1]}", "false_flags_per_patient_day": round(v[2] / 150, 2)} for k, v in tot.items()}
    rep = {"note": "Simulated BP/HRV, monitoring-only scores; engineering test, not clinical validation.",
           "summary": summary, "per_patient": out}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/bp_hrv_report.json").write_text(json.dumps(rep, indent=1))
    return rep


if __name__ == "__main__":
    generate()
    r = evaluate()
    for k, v in r["summary"].items(): print(f"{k:6s} events flagged {v['events_flagged']}  false flags/pt-day {v['false_flags_per_patient_day']}")
    for pid, v in r["per_patient"].items():
        print(pid, v["baseline"], {k: (v[k]["event_flagged"], v[k]["max_score_in_event"], v[k]["false_flags_per_day"]) for k in ("sbp", "shock", "hrv")})
