"""Layers 5-7: textual physiological state manifest, 264-slot context-adaptive encoder, hybrid PINN-ODE digital twin
(ensemble), validity gate and counterfactual branches.

Twin dynamics in normalised deviation space z = (x - baseline) / S, S = [10 bpm, 3 /min, 2 %, 0.5 C]:
    dz/dt = -z / tau  +  [alpha_T * z_temp + alpha_A * activity]_HR  +  r_theta(z, trend, activity, context)
- relaxation to the personal baseline (stable mechanistic prior; tau learned, positive)
- HR coupling to temperature and activity: the illustrative V4.1 equation (alpha learned, not invented)
- r_theta: neural residual (MLP), penalised so mechanistic terms dominate (physics-informed loss)
Fixed-step RK4, dt = 15 s, horizons 300 s (primary), 900 s (secondary), 1800 s (experimental).
Equations are PROVISIONAL pending clinical/AI approval; forecasts are experimental and cannot change priority.
Run: python twin.py  -> model/twin.pt, results/twin_report.json
"""
import hashlib, json, math, time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V = ("hr", "rr", "spo2", "temp")
S = torch.tensor([10.0, 3.0, 2.0, 0.5])
FRAME, HOR = 15, {"5min": 20, "15min": 60, "30min": 120}
BOUNDS = {"hr": (20, 250), "rr": (0, 70), "spo2": (50, 100), "temp": (30, 43)}
CTX_KEYS = ("respiratory", "cardiac", "infection")
EQUATION_SET = "avoflare-twin-eq-0.1-provisional"
REG = json.loads((ROOT / "MineArena_V4_1_Integration_Update/06_ai_digital_twin/02_encoder_feature_registry.json").read_text())


# ---------------- PINN-ODE ----------------
class Twin(nn.Module):
    def __init__(self, n_in=4 + 4 + 1 + 4):
        super().__init__()
        self.log_tau = nn.Parameter(torch.full((4,), math.log(math.expm1(1.0))))   # tau = softplus * 600 s
        self.alpha = nn.Parameter(torch.zeros(2))                                    # HR <- temp, activity
        self.res = nn.Sequential(nn.Linear(n_in, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 4))

    def f(self, z, trend, act, ctx):
        tau = nn.functional.softplus(self.log_tau) * 600.0
        mech = -z / tau
        mech = mech + torch.stack([self.alpha[0] * z[:, 3] / 600 + self.alpha[1] * act / 600] + [torch.zeros_like(act)] * 3, 1)
        r = torch.tanh(self.res(torch.cat([z, trend, act[:, None], ctx], 1))) / 60.0      # bounded residual (per s)
        return mech + r, r

    def rollout(self, z0, trend, act, ctx, steps, dt=FRAME):
        z, out, rs = z0, [], []
        for _ in range(steps):
            k1, r = self.f(z, trend, act, ctx); k2, _ = self.f(z + dt / 2 * k1, trend, act, ctx)
            k3, _ = self.f(z + dt / 2 * k2, trend, act, ctx); k4, _ = self.f(z + dt * k3, trend, act, ctx)
            z = z + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4); out.append(z); rs.append(r)
        return torch.stack(out, 1), torch.stack(rs, 1)


def frames(pid, data=HERE / "data"):
    """15 s causal frames: median per vital, activity fraction, causal 6 h rolling-median baseline."""
    import pandas as pd
    d = dict(np.load(data / f"{pid}.npz"))
    n = len(d["hr"]) // FRAME
    x = np.stack([np.nanmedian(d[v][: n * FRAME].reshape(n, FRAME), 1) if np.isfinite(d[v]).any() else np.full(n, np.nan) for v in V], 1)
    act = d["activity"][: n * FRAME].reshape(n, FRAME).mean(1) if "activity" in d else np.zeros(n)
    b = pd.DataFrame(x).rolling(1440, min_periods=240).median().shift(1).to_numpy()   # past only
    return x.astype(np.float32), b.astype(np.float32), act.astype(np.float32)


def ctx_vec(ctx):
    return np.array([float(ctx["history"].get(k, False)) for k in CTX_KEYS] + [ctx.get("age", 50) / 100], np.float32)


def make_windows(x, b, act, cvec, idx, steps):
    z = (x - b) / S.numpy()
    I = np.array([i for i in idx if i >= 20 and i + steps < len(x) and np.isfinite(z[i]).sum() >= 3 and np.isfinite(b[i]).all()])
    if len(I) == 0: return None
    z0 = np.nan_to_num(z[I]); tr = np.nan_to_num(z[I] - z[I - 20])
    Y = np.stack([z[i + 1: i + 1 + steps] for i in I])
    return dict(z0=z0, tr=tr, act=act[I], ctx=np.repeat(cvec[None], len(I), 0), Y=Y, I=I)


def train_member(args):
    W, seed = args; iters, lam = 400, 0.05
    torch.set_num_threads(2); torch.manual_seed(seed); m = Twin(); opt = torch.optim.Adam(m.parameters(), 3e-3)
    T = {k: torch.tensor(v) for k, v in W.items() if k != "I"}
    n = len(T["z0"])
    for it in range(iters):
        j = torch.randint(0, n, (256,))
        pred, r = m.rollout(T["z0"][j], T["tr"][j], T["act"][j], T["ctx"][j], HOR["15min"])   # train on 15 min, evaluate to 30
        y = T["Y"][j][:, :HOR["15min"]]; mask = torch.isfinite(y)
        data = ((pred - torch.nan_to_num(y)) ** 2)[mask].mean()
        loss = data + lam * (r * 60).pow(2).mean()                       # physics-informed: residual kept small
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
    return m


class Ensemble:
    def __init__(self, members, ood, cal=None):
        self.members, self.ood, self.cal = members, ood, cal

    @torch.no_grad()
    def forecast(self, x_now, x_5min_ago, base, act, ctx, steps=HOR["30min"]):
        """Returns per-horizon mean/sd in physical units, or abstention with reason (validity gate)."""
        if base is None or any(v is None for v in base): return {"status": "abstained", "reason": "baseline not established"}
        avail = [v is not None for v in x_now]
        if sum(avail) < 3: return {"status": "abstained", "reason": "fewer than three current vitals available"}
        b = np.array(base, np.float32)
        z0 = np.array([0 if v is None else (v - b[i]) / S[i].item() for i, v in enumerate(x_now)], np.float32)
        zp = np.array([0 if (v is None or x_now[i] is None) else (v - b[i]) / S[i].item() for i, v in enumerate(x_5min_ago)], np.float32)
        tr = z0 - zp
        dist = float(np.sqrt((((np.r_[z0, tr] - self.ood["mu"]) / self.ood["sd"]) ** 2).sum()))
        if dist > self.ood["thr"]: return {"status": "abstained", "reason": f"input outside training distribution (distance {dist:.1f})"}
        T = lambda a: torch.tensor(a)[None]
        P = torch.stack([m.rollout(T(z0), T(tr), torch.tensor([act], dtype=torch.float32), T(ctx), steps)[0][0] for m in self.members])
        X = P * S + torch.tensor(b)                                      # members x steps x 4
        if not torch.isfinite(X).all(): return {"status": "abstained", "reason": "solver produced non-finite state"}
        mu, sd = X.mean(0).numpy(), X.std(0).numpy()
        if self.cal is not None:                                         # calibrated: mean +/- 2*sd is the 95% band
            sd = ((P.std(0).numpy() + self.cal["floor"]) * self.cal["mult"][:steps] * S.numpy() / 2).astype(np.float32)
        for i, v in enumerate(V):
            lo, hi = BOUNDS[v]
            if (mu[:, i] < lo).any() or (mu[:, i] > hi).any(): return {"status": "abstained", "reason": f"{v} forecast out of physical bounds"}
        out = {"status": "experimental", "equation_set": EQUATION_SET, "ood_distance": round(dist, 2), "trajectory": {
            v: {"mean": mu[:, i].round(2).tolist(), "sd": sd[:, i].round(2).tolist(), "available": avail[i]} for i, v in enumerate(V)},
            "horizons": {h: {v: {"mean": round(float(mu[k - 1, i]), 2), "sd": round(float(sd[k - 1, i]), 2)} for i, v in enumerate(V)}
                         for h, k in HOR.items() if k <= steps}}
        return out

    def params(self):
        tau = np.mean([(nn.functional.softplus(m.log_tau) * 600).detach().numpy() for m in self.members], 0)
        al = np.mean([m.alpha.detach().numpy() for m in self.members], 0)
        return {"tau_s": {v: round(float(x), 1) for v, x in zip(V, tau)}, "alpha_hr_temp": round(float(al[0]), 4),
                "alpha_hr_activity": round(float(al[1]), 4), "status": "learned_provisional"}


def save(ens, path=HERE / "model/twin.pt"):
    torch.save({"state": [m.state_dict() for m in ens.members], "ood": ens.ood}, path)


def load(path=HERE / "model/twin.pt"):
    if not path.exists(): return None
    ck = torch.load(path, weights_only=False)
    ms = []
    for s in ck["state"]:
        m = Twin(); m.load_state_dict(s); m.eval(); ms.append(m)
    return Ensemble(ms, ck["ood"], ck.get("cal"))


# ---------------- Manifest + encoder ----------------
def manifest(pid, session, t, dec, engine_state, ctx, parent=None, forecast=None):
    ex = dec["experts"]
    m = {"schema_version": "manifest-1.0", "identity": {"source_namespace": ctx.get("namespace", "synthea"), "subject": pid,
         "variant": "original", "session": session}, "source_time_s": int(t),
         "context_ref": f"context/{pid}/v1", "state_version": dec["state_version"], "parent_manifest_ref": parent,
         "observed_state": {v: {"value": ex[v]["value"], "unit": ex[v]["unit"], "score": ex[v]["score"],
                                "quality": ex[v]["quality"], "fresh": ex[v]["fresh"]} for v in V},
         "baseline_state": {v: {"value": ex[v]["baseline"], "status": ex[v]["baseline_status"],
                                "frozen": engine_state.base[v].frozen, "version": engine_state.base[v].version} for v in V},
         "physiological_relationships": relationships(ex),
         "model_configuration": {"equation_set": EQUATION_SET, "approval": "provisional", "solver": "RK4 dt=15s"},
         "expert_evidence_refs": [f"expert/{v}/{dec['state_version']}" for v in V],
         "rules": dec["rules"],
         "uncertainty": {"missing": [v for v in V if ex[v]["value"] is None],
                         "suspect": [v for v in V if ex[v]["quality"] in ("suspect", "artifact")],
                         "baseline_unavailable": [v for v in V if ex[v]["baseline"] is None]},
         "estimated_state_ref": None if not forecast or forecast.get("status") != "experimental" else f"twin/{pid}/{dec['state_version']}"}
    m["semantic_hash"] = hashlib.sha256(json.dumps(m, sort_keys=True, default=str).encode()).hexdigest()[:16]
    m["manifest_id"] = f"{pid}-{session}-{dec['state_version']}"
    return m


def relationships(ex):
    rel = []
    def d(v): return ex[v]["delta"] or 0
    if d("spo2") < -1 and d("rr") > 1: rel.append({"id": "REL-RESP-1", "text": "falling SpO2 with rising RR", "status": "supported"})
    if d("temp") > 0.3 and d("hr") > 5: rel.append({"id": "REL-THERM-1", "text": "rising temperature with rising HR", "status": "supported"})
    if d("hr") > 10 and d("spo2") < -1: rel.append({"id": "REL-CV-1", "text": "rising HR with falling SpO2", "status": "possible"})
    return rel or [{"id": "REL-NONE", "text": "no cross-vital relationship currently supported", "status": "unknown"}]


def encode(dec, eng, ctx):
    """264-slot vector + availability masks following 02_encoder_feature_registry.json ordering (proposal semantics)."""
    vec = np.zeros(264, np.float32); ex = dec["experts"]
    names = {f["name"]: f for f in REG["features"]}
    hist = {v: [b for a, b in eng.hist[v] if dec["t"] - a <= 60] for v in V}
    val = {}
    for v in V:
        h, e, k = hist[v], ex[v], "temperature" if v == "temp" else v
        val.update({f"{k}.latest": e["value"], f"{k}.median": np.median(h) if h else None, f"{k}.minimum": min(h) if h else None,
                    f"{k}.maximum": max(h) if h else None, f"{k}.std": float(np.std(h)) if len(h) > 1 else None,
                    f"{k}.slope_1min": e["slope60"], f"{k}.slope_5min": e["slope300"], f"{k}.baseline": e["baseline"],
                    f"{k}.delta": e["delta"], f"{k}.robust_z": e["z"], f"{k}.abnormal_duration": e["cand_seconds"],
                    f"{k}.freshness": 1.0 if e["fresh"] else 0.0,
                    f"{k}.quality.present": float(e["value"] is not None), f"{k}.quality.valid": float(e["quality"] == "valid"),
                    f"{k}.quality.suspect": float(e["quality"] == "suspect"), f"{k}.quality.invalid": float(e["quality"] == "invalid"),
                    f"{k}.quality.missing_fraction": 1 - e["valid_frac"],
                    f"{k}.expert.component_score": e["score"], f"{k}.expert.concern": e["concern"],
                    f"{k}.expert.baseline_delta": e["delta"], f"{k}.expert.trend_slope": e["slope60"],
                    f"{k}.expert.abnormal_duration": e["cand_seconds"],
                    f"{k}.temporal.baseline_established": float(e["baseline_status"] == "established"),
                    f"{k}.temporal.baseline_frozen": float(eng.base[v].frozen),
                    f"{k}.temporal.calibration_fraction": min(1.0, eng.base[v].run / 900),
                    f"{k}.temporal.baseline_available": float(e["baseline"] is not None)})
    val.update({"context.age_at_discharge": ctx.get("age"), "context.domain_respiratory": float(ctx["history"]["respiratory"]),
                "context.domain_cardiovascular": float(ctx["history"]["cardiac"]), "context.domain_infectious": float(ctx["history"]["infection"])})
    filled = 0
    for name, f in names.items():
        x = val.get(name)
        if x is not None and np.isfinite(x):
            vec[f["index"]] = x; filled += 1
            if f.get("availability_mask_index") is not None: vec[f["availability_mask_index"]] = 1.0
    return vec, filled


def counterfactuals(ens, ex, base, act, ctx, x5):
    """Isolated branches (07_trustworthy): A original, B exclude suspect observations, C measurement +/- sensor noise,
    D parameter tau x0.8 / x1.2. Never mutates patient state, alerts or records."""
    cur = [ex[v]["value"] for v in V]
    out = {"A_original": ens.forecast(cur, x5, base, act, ctx, HOR["15min"])}
    sus = [None if ex[v]["quality"] in ("suspect", "artifact") else ex[v]["value"] for v in V]
    out["B_exclude_suspect"] = ens.forecast(sus, x5, base, act, ctx, HOR["15min"]) if sus != cur else {"status": "not_applicable", "reason": "no suspect observation"}
    noise = [1.0, 1.0, 1.0, 0.1]
    for sign, k in ((1, "C_measurement_plus"), (-1, "C_measurement_minus")):
        out[k] = ens.forecast([None if c is None else c + sign * n for c, n in zip(cur, noise)], x5, base, act, ctx, HOR["15min"])
    saved = [m.log_tau.data.clone() for m in ens.members]
    for f, k in ((0.8, "D_tau_x0.8"), (1.2, "D_tau_x1.2")):
        for m, s0 in zip(ens.members, saved):
            m.log_tau.data = torch.log(torch.expm1(nn.functional.softplus(s0) * f))
        out[k] = ens.forecast(cur, x5, base, act, ctx, HOR["15min"])
    for m, s0 in zip(ens.members, saved): m.log_tau.data = s0
    ref = out["A_original"]
    for k, r in out.items():
        if r.get("status") == "experimental" and ref.get("status") == "experimental":
            r["divergence_15min"] = {v: round(r["horizons"]["15min"][v]["mean"] - ref["horizons"]["15min"][v]["mean"], 2) for v in V}
        r.pop("trajectory", None)
    return out


# ---------------- training + evaluation ----------------
def main():
    from engine import load_context
    t0 = time.time(); C = load_context()
    train_p, test_p = ["P001", "P002", "P003", "P004", "P005", "P006", "P007"], ["P008", "P009", "P010"]
    rng = np.random.default_rng(0)
    labels = {l["patient_id"]: l for l in json.loads((HERE / "data/labels.json").read_text())}
    F = {p: frames(p) for p in train_p + test_p}

    def idx_for(p, n_rand):
        x = F[p][0]; idx = set(rng.integers(240, len(x) - 130, n_rand).tolist())
        for ev in labels[p]["events"]:                       # oversample deterioration periods
            idx |= set(range(ev["onset_t"] // FRAME - 120, ev["recovered_t"] // FRAME, 2))
        return sorted(idx)
    parts = [make_windows(*F[p], ctx_vec(C[p]), idx_for(p, 6000), HOR["30min"]) for p in train_p]
    W = {k: np.concatenate([w[k] for w in parts if w]) for k in parts[0]}
    feats = np.c_[W["z0"], W["tr"]]
    ood = {"mu": feats.mean(0), "sd": feats.std(0) + 1e-3}
    ood["thr"] = float(np.percentile(np.sqrt((((feats - ood["mu"]) / ood["sd"]) ** 2).sum(1)), 99.9))
    from multiprocessing import Pool
    with Pool(4) as pool: members = pool.map(train_member, [(W, s) for s in range(4)])
    ens = Ensemble(members, ood); (HERE / "model").mkdir(exist_ok=True); save(ens)

    # held-out evaluation: synthetic test patients + real BIDMC numerics
    def evaluate(x, b, act, cvec, idx):
        w = make_windows(x, b, act, cvec, idx, HOR["30min"])
        if w is None: return None
        T = {k: torch.tensor(v) for k, v in w.items() if k != "I"}
        with torch.no_grad():
            P = torch.stack([m.rollout(T["z0"], T["tr"], T["act"], T["ctx"], HOR["30min"])[0] for m in members])
            mech = Twin(); mech.load_state_dict(members[0].state_dict())
            for p_ in mech.res.parameters(): p_.data.zero_()
            M = mech.rollout(T["z0"], T["tr"], T["act"], T["ctx"], HOR["30min"])[0]
        mu, sd = P.mean(0), P.std(0) + 1e-6
        res = {}
        for h, k in HOR.items():
            y = T["Y"][:, k - 1]; ok = torch.isfinite(y)
            e = lambda pred: [round(float((((pred[:, k - 1] - y).abs() * S))[:, i][ok[:, i]].mean()), 3) for i in range(4)]
            persist = T["z0"]
            cover = (((mu[:, k - 1] - y).abs() <= 2 * (sd[:, k - 1] + 0.1)) & ok).sum(0) / ok.sum(0)
            res[h] = {"n": int(ok.any(1).sum()), "mae_twin": dict(zip(V, e(mu))), "mae_persistence": dict(zip(V, e(persist[:, None].expand_as(mu)))),
                      "mae_mechanistic_only": dict(zip(V, e(M))), "coverage_2sd": dict(zip(V, [round(float(c), 3) for c in cover]))}
        return res
    report = {"equation_set": EQUATION_SET, "params": ens.params(), "train_patients": train_p, "test_patients": test_p,
              "ensemble": len(members), "training_windows": int(len(W["z0"])), "ood_threshold": round(ood["thr"], 2), "results": {}}
    for p in test_p:
        x, b, a = F[p]
        allidx = list(range(240, len(x) - 130, 20))
        ev = [i for e in labels[p]["events"] for i in range(e["onset_t"] // FRAME, e["recovered_t"] // FRAME, 2)]
        report["results"][p] = {"all": evaluate(x, b, a, ctx_vec(C[p]), allidx), "deterioration": evaluate(x, b, a, ctx_vec(C[p]), ev) if ev else None}
    report["results"]["BIDMC_real"] = {"status": "not_evaluated", "reason": "BIDMC records are ~8 min; a 5 min history plus 5 min horizon does not fit. BIDMC is replayed through the clinical pipeline instead."}
    report["train_seconds"] = round(time.time() - t0)
    (HERE / "results/twin_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({p: r["all"]["15min"] if r.get("all") else r for p, r in report["results"].items()}, indent=0)[:3000])
    print(report["params"])


def load_bidmc():
    """BIDMC numerics (real, 1 Hz, HR/RR/SpO2, no temperature) -> 15 s frames; baseline = causal running median."""
    import pandas as pd
    df = pd.read_csv(ROOT / "04_simulation/04_simulation/bidmc_analysis/replay_numerics.csv", dtype={"record": str})
    out = {}
    for rec, g in df.groupby("record"):
        n = len(g) // FRAME
        if n < 200: continue
        arr = np.stack([g["hr_bpm"].to_numpy(float), g["rr_per_min"].to_numpy(float), g["spo2_pct"].to_numpy(float), np.full(len(g), np.nan)], 1)
        x = np.nanmedian(arr[: n * FRAME].reshape(n, FRAME, 4), 1).astype(np.float32)
        b = pd.DataFrame(x).expanding(min_periods=20).median().shift(1).to_numpy().astype(np.float32)
        b[:, 3] = 37.0; x[:, 3] = np.nan                     # temperature unavailable in BIDMC: masked, not fabricated
        out[rec] = (x, b, np.zeros(n, np.float32))
    return out


if __name__ == "__main__":
    main()
