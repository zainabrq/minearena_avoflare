"""15-day, 10-samples/s wearable simulator for the 10 Synthea patients.

Source: 02_patient_data/patient_physiological_configuration_v1_1.json (scenario knots,
initial vitals, AR(1) rho, physiological/sensor SD). Engineering simulation, NOT clinical data.
Device emits 10 pps; the gateway aggregates each second (median of valid samples) -> 1 Hz stream.
Scenario labels are written to labels.json and are offline-only (never read by the engine).
"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.signal import lfilter

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "02_patient_data/patient_physiological_configuration_v1_1.json").read_text())
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "data"
DAYS, PPS, V = 15, 10, ("hr", "rr", "spo2", "temp")
N = DAYS * 86400
CRIT = {"hr": lambda x: (x >= 131) | (x <= 40), "rr": lambda x: (x >= 25) | (x <= 8),
        "spo2": lambda x: x <= 91, "temp": lambda x: (x >= 39.1) | (x <= 35.0)}


def ramp(n, a):  # trapezoid envelope: 60 s ramps
    r = min(60, n // 2)
    e = np.ones(n) * a
    e[:r] *= np.linspace(0, 1, r); e[n - r:] *= np.linspace(1, 0, r)
    return e


def simulate(p, seed):
    rng = np.random.default_rng(seed)
    base = p["initial_vitals"]
    t = np.arange(N)
    hod = (t % 86400) / 3600.0
    circ = np.cos((hod - 16) / 24 * 2 * np.pi)          # peak 16:00, trough 04:00
    lat = {"hr": base["hr"] + 4 * circ, "rr": base["rr"] + 0.8 * circ,
           "spo2": np.full(N, float(base["spo2"])), "temp": base["temp"] + 0.25 * circ}
    activity = np.zeros(N, bool)
    for d in range(DAYS):                                # walking / ADL bursts (benign confounders)
        for _ in range(rng.integers(3, 7)):
            s = d * 86400 + int(rng.uniform(7, 21) * 3600); n = int(rng.uniform(300, 1200))
            activity[s:s + n] = True
            lat["hr"][s:s + n] += ramp(n, rng.uniform(12, 28))
            lat["rr"][s:s + n] += ramp(n, rng.uniform(2, 5))
            lat["temp"][s:s + n] += ramp(n, 0.1)
    # deterioration scenario (patient's own knots) placed on a seeded day
    sc, label = p["scenario"], {"patient_id": p["patient_id"], "scenario": p["scenario"]["id"], "events": []}
    if sc["onset_s"] is not None:
        start = int(rng.integers(2, 13)) * 86400 + int(rng.uniform(0, 86400))
        kt = np.array([k["t_s"] for k in sc["knots"]]); last = int(kt[-1])
        hold, rec = 1800, 3600
        seg = np.arange(last + hold + rec)
        for v in V:
            kv = np.array([k["target"][v] for k in sc["knots"]]) - sc["knots"][0]["target"][v]
            d = np.interp(np.minimum(seg, last), kt, kv)
            d[last + hold:] *= np.linspace(1, 0, rec)        # treated -> recovery
            sl = slice(start, min(N, start + len(seg)))
            lat[v][sl] += d[: sl.stop - sl.start]
        label["events"].append({"onset_t": start + sc["onset_s"], "end_t": start + last + hold,
                                "recovered_t": start + last + hold + rec})
    for v in V:                                          # AR(1) physiological variability
        rho, sd = CFG["defaults"]["ar1_rho"][v], p["physiological_sd"][v]
        lat[v] = lat[v] + lfilter([np.sqrt(1 - rho ** 2) * sd], [1, -rho], rng.standard_normal(N))
    lat["spo2"] = np.clip(lat["spo2"], 0, 100)
    for ev in label["events"]:                           # severe endpoint from latent truth
        o, e = ev["onset_t"], ev["end_t"]
        hit = np.zeros(e - o, bool)
        for v in V:
            hit |= CRIT[v](lat[v][o:e])
        # severe = first time latent truth stays critical for 60 s
        run = np.convolve(hit, np.ones(60), "valid") >= 60
        ev["severe_t"] = int(o + np.argmax(run)) if run.any() else None
    # 10 pps device samples -> per-second gateway median
    obs, motion, fault = {}, np.zeros(N, bool), np.zeros(N, bool)
    sn = CFG["defaults"]["sensor_noise_sd"]
    for v in V:
        x = np.repeat(lat[v].astype(np.float32), PPS).reshape(N, PPS)
        x += rng.normal(0, sn[v] * 2, x.shape).astype(np.float32)
        x = np.round(x, 2) if v == "temp" else np.round(x)
        if v == "spo2": x = np.clip(x, 0, 100)
        obs[v] = np.median(x, axis=1).astype(np.float32)
    for d in range(DAYS):
        for _ in range(rng.poisson(4)):                  # motion spikes on SpO2 (+HR)
            s = d * 86400 + int(rng.uniform(0, 86400)); n = int(rng.integers(2, 6))
            obs["spo2"][s:s + n] -= rng.uniform(10, 25)
            if rng.random() < 0.5: obs["hr"][s:s + n] += rng.uniform(30, 50)
            motion[s:s + n] = rng.random() < 0.6           # device accelerometer flag (not always present)
        for _ in range(rng.poisson(0.7)):                # probe removal: SpO2 lost, HR flatline, sensor-off flag
            s = d * 86400 + int(rng.uniform(0, 86400)); n = int(rng.integers(30, 180))
            obs["spo2"][s:s + n] = np.nan; obs["hr"][s:s + n] = obs["hr"][s - 1]; fault[s:s + n] = True
        for _ in range(rng.poisson(2)):                  # BLE dropout: everything missing
            s = d * 86400 + int(rng.uniform(0, 86400)); n = int(rng.integers(10, 120))
            for v in V: obs[v][s:s + n] = np.nan
    for f in sc["faults"]:                               # scenario-declared faults (P010)
        s = label["events"][0]["onset_t"] - sc["onset_s"] + f["start_s"]
        obs[f["channel"]][s:s + f["duration_s"]] = np.nan; fault[s:s + f["duration_s"]] = True
    obs["spo2"] = np.clip(obs["spo2"], 0, 100)
    label["artifact_seconds"] = int((motion | fault).sum())
    return obs, motion, fault, activity, label


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    labels = []
    for i, p in enumerate(CFG["patients"]):
        obs, motion, fault, act, lab = simulate(p, CFG["seed"] * 100 + i)
        np.savez_compressed(OUT / f"{p['patient_id']}.npz", **obs, motion=motion, fault=fault, activity=act)
        labels.append(lab)
        print(p["patient_id"], lab["scenario"], lab["events"])
    (OUT / "labels.json").write_text(json.dumps(labels, indent=1))
    (OUT / "README.txt").write_text(
        "Generated by mineareana/avoflare/sim.py. 10 patients x 15 days. Device 10 pps -> gateway 1 Hz median.\n"
        "Arrays: hr rr spo2 temp (float32, NaN=missing), motion/fault/activity (device flags). Index = source second.\n"
        "labels.json is OFFLINE ground truth for evaluation only. Synthetic engineering data, not clinical data.\n")


if __name__ == "__main__":
    main()
