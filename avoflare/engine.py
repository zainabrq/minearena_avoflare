"""Avoflare V4.1 clinical engine: quality/artifact (06), partial NEWS2 (03), personalized baseline (04),
physiological experts 2-5 (05), patient context expert 1 (01), safety + temporal decision policy (07),
alert lifecycle, and a fixed NEWS2 comparator. Clinical decision support prototype - not diagnosis.
All thresholds are the spec's configurable engineering defaults, not clinical guidelines.
"""
from collections import deque
from decimal import Decimal, ROUND_HALF_UP
import json, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
V = ("hr", "rr", "spo2", "temp")
UNIT = {"hr": "/min", "rr": "/min", "spo2": "%", "temp": "Cel"}
PRI = {0: "None", 1: "Watch", 2: "Review", 3: "Urgent"}
POLICY = "avoflare-policy-1.1"
WINDOW_S = 10
FRESH_S = 15
# personalization (deliberate, documented deviation from CLIN-2): a score-2 value lying inside the
# patient's own baseline range (|z| < PERS_Z and |delta| < candidate magnitude, sec.04) is Watch, not Review. SAFE-1 never affected.
PERS_Z = 3.0
ML_THRESHOLD = None          # set from trained model metadata; ML can raise to Review only (ML-1)


# ---------------- 03 partial NEWS2 ----------------
def rhu(x, nd=0):
    if nd == 0 and x >= 0:
        return float(math.floor(x + 0.5))       # exact for sensor floats; Decimal path for temperature
    q = Decimal(1) if nd == 0 else Decimal("0.1")
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def band(vital, x, scale=1, o2="unknown"):
    if x is None:
        return None
    x = rhu(x, 1 if vital == "temp" else 0)
    if vital == "hr":
        return 3 if x <= 40 else 1 if x <= 50 else 0 if x <= 90 else 1 if x <= 110 else 2 if x <= 130 else 3
    if vital == "rr":
        return 3 if x <= 8 else 1 if x <= 11 else 0 if x <= 20 else 2 if x <= 24 else 3
    if vital == "temp":
        return 3 if x <= 35.0 else 1 if x <= 36.0 else 0 if x <= 38.0 else 1 if x <= 39.0 else 2
    if scale == 1:
        return 3 if x <= 91 else 2 if x <= 93 else 1 if x <= 95 else 0
    if x <= 83: return 3
    if x <= 85: return 2
    if x <= 87: return 1
    if x <= 92: return 0
    if o2 == "off": return 0
    if o2 == "on": return 1 if x <= 94 else 2 if x <= 96 else 3
    return None                                   # >=93 with unknown oxygen status: unscorable


def clinical_score(values, scale=1, o2="unknown"):
    comp = {v: band(v, values.get(v), scale, o2) for v in V}
    s = [c for c in comp.values() if c is not None]
    return {"components": comp, "observed_subtotal": sum(s) if s else None, "scored_count": len(s),
            "maximum_available_subtotal": 3 * len(s), "theoretical_maximum": 12, "full_news2_score": None,
            "maximum_component_score": max(s) if s else None,
            "missing_or_unscorable": [v for v in V if comp[v] is None], "spo2_scale": scale,
            "status": "complete_four" if len(s) == 4 else "partial" if s else "unavailable"}


def raw_extreme(v, x, scale=1):
    return {"hr": x <= 40 or x >= 131, "rr": x <= 8 or x >= 25, "temp": x <= 35.0,
            "spo2": x <= (91 if scale == 1 else 83)}[v]


# ---------------- 01 patient context expert ----------------
KW = {"respiratory": ("copd", "emphysema", "asthma", "bronchitis", "pneumonia", "respiratory", "coronavirus",
                      "dyspnea", "covid", "pulmonary"),
      "cardiac": ("heart failure", "coronary", "myocardial", "atrial fibrillation", "ischemic heart", "cardiac",
                  "angina", "arrhythmia"),
      "infection": ("pneumonia", "sepsis", "infection", "appendicitis", "coronavirus", "fever", "cellulitis")}


def load_context():
    kb = json.loads((ROOT / "02_patient_data/patient_kb_v1.json").read_text())
    ctx = {}
    for p in kb["patients"]:
        labels = [c["label"].lower() for c in p.get("conditions", [])]
        facts = {k: sorted({l for l in labels if any(w in l for w in ws)}) for k, ws in KW.items()}
        ctx[p["patient_id"]] = {
            "patient_id": p["patient_id"], "fhir_patient_id": p["fhir_patient_id"], "age": p["age_at_discharge"],
            "gender": p["gender"], "history": {k: bool(f) for k, f in facts.items()}, "facts": facts,
            "beta_blocker_history": bool(p.get("beta_blocker_history")),
            "current_medication_use": p.get("current_medication_use", "unknown"),
            "spo2_scale": 1, "o2": "unknown",
            "limitations": ["Historical conditions are evidence, not verified active diagnoses",
                            "Discharge disposition unknown", "Scale 1 default: no verified Scale 2 authorization"]}
    return ctx


RELEVANT = {"hr": "cardiac", "rr": "respiratory", "spo2": "respiratory", "temp": "infection"}
CAND = {"hr": 15, "rr": 4, "spo2": 3, "temp": 0.5}         # 04 candidate deviation magnitudes
FLOOR = {"hr": 1, "rr": 1, "spo2": 0.5, "temp": 0.1}
JUMP = {"hr": 30, "rr": 10, "spo2": 5, "temp": 0.5}        # 06 motion/outlier candidate


_TRIC = {}


def _TRI(n):
    if n not in _TRIC: _TRIC[n] = np.triu_indices(n, 1)
    return _TRIC[n]


def theil_sen(t, y):
    if len(t) < 3 or t[-1] - t[0] < 30:
        return None
    step = max(1, len(t) // 30)                  # ~30 points keeps Theil-Sen cheap
    t, y = np.asarray(t[::step], float), np.asarray(y[::step], float)
    i, j = _TRI(len(t))
    dt = t[j] - t[i]
    return float(np.median((y[j] - y[i]) / dt) * 60) if len(dt) else None


class Baseline:
    """04: median/MAD reference from >=900 contiguous eligible seconds; freeze on concern.
    Tuned default: after calibration the reference is the trailing 6 h of eligible data (1 sample / 10 s) so a
    1-2 h deterioration cannot drift into the reference (spec default 1800 s adapted too fast)."""
    def __init__(self, v):
        self.v, self.buf, self.run, self.status = v, deque(maxlen=2160), 0, "unestablished"
        self.ref = self.scale = None; self.frozen = False; self.stable_run = 0; self.version = 0

    def feed(self, t, x, eligible, concern):
        if concern:
            self.frozen, self.stable_run = True, 0
            if self.status == "calibrating": self.run = 0
            return
        if not eligible:
            self.run = 0; self.stable_run = 0
            if self.status != "established": self.buf.clear()     # no summing disconnected segments
            return
        self.stable_run += 1
        if self.frozen and self.stable_run < 60:
            return
        self.frozen = False
        self.run += 1
        if self.status != "established" or self.run % 10 == 0: self.buf.append(x)
        if self.status != "established":
            self.status = "calibrating"
            if self.run >= 900: self._update(); self.status = "established"
        elif self.run % 30 == 0:
            self._update()

    def _update(self):
        a = np.fromiter(self.buf, float)
        self.ref = float(np.median(a)); mad = float(np.median(np.abs(a - self.ref)))
        self.scale = max(1.4826 * mad, FLOOR[self.v]); self.version += 1

    def z(self, x):
        if self.status != "established" or x is None: return None, None
        d = x - self.ref
        return d, d / self.scale


class PatientEngine:
    """Per-session engine. feed() one gateway second; returns ClinicalDecision at each window close."""
    def __init__(self, ctx, model=None, personalize=True):
        self.ctx, self.model, self.personalize = ctx, model, personalize
        self.scale, self.o2 = ctx["spo2_scale"], ctx["o2"]
        self.base = {v: Baseline(v) for v in V}
        self.last_valid = {v: (None, None) for v in V}         # (t, value)
        self.suspect_run = {v: None for v in V}                 # (start_t, pre_value)
        self.hist = {v: deque(maxlen=300) for v in V}          # (t, value) valid, 5 min
        self.cand = {v: deque(maxlen=30) for v in V}           # per-second candidate flags
        self.cand_run = {v: 0 for v in V}
        self.flat = {v: (None, 0) for v in V}
        self.qcount = {v: deque(maxlen=WINDOW_S) for v in V}
        self.recent_activity = -10 ** 9
        self.safety = (0, None); self.tech = None; self.ml_run = 0
        self.t = None; self.seen = set(); self.state_version = 0; self.wv = deque(maxlen=181)

    # ---- 06 quality ----
    def _quality(self, t, v, x, motion, fault):
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "missing", ["missing"]
        if not math.isfinite(x) or x < 0 or (v == "spo2" and x > 100):
            return "invalid", ["out_of_range"]
        if v == "temp" and not 20 <= x <= 50:
            return "suspect", ["temp_sensor_range"]
        if fault and v in ("hr", "spo2"):
            return "artifact", ["device_sensor_off_confirmed"]
        if x == 0 and v != "temp":
            return "suspect", ["zero_value"]
        fv, n = self.flat[v]
        self.flat[v] = (x, n + 1) if fv is not None and abs(fv - x) < (0.01 if v == "temp" else 0.1) else (x, 1)
        sr = self.suspect_run[v]
        if sr is not None:
            start, pre = sr
            if abs(x - pre) < JUMP[v] / 2:
                self.suspect_run[v] = None                        # reversal -> spike was transient
            elif t - start < 10:
                return "suspect", ["abrupt_change_unresolved"] + (["motion_flag"] if motion else [])
            else:
                self.suspect_run[v] = None                        # sustained >10 s: treat as genuine
        lt, lv = self.last_valid[v]
        if lt is not None and t - lt <= 2 and abs(x - lv) >= JUMP[v]:
            self.suspect_run[v] = (t, lv)
            return "suspect", ["abrupt_change"] + (["motion_flag"] if motion else [])
        return "valid", (["flatline_suspect"] if self.flat[v][1] >= 10 and v == "hr" else [])

    def feed(self, t, obs, motion=False, fault=False, activity=False, event_id=None):
        if event_id is not None:                              # idempotent duplicates (ALERT-08)
            if event_id in self.seen: return None
            self.seen.add(event_id)
        if self.t is not None and t <= self.t:
            return None                                       # out-of-order cannot overwrite newer state
        self.t = t
        if activity: self.recent_activity = t
        q = {}
        safety, sreason = 0, []
        for v in V:
            x = obs.get(v)
            x = None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
            qual, why = self._quality(t, v, x, motion, fault)
            q[v] = (qual, x, why)
            self.qcount[v].append(qual)
            if qual == "valid":
                self.last_valid[v] = (t, x); self.hist[v].append((t, x))
                if raw_extreme(v, x, self.scale) or band(v, x, self.scale, self.o2) == 3 and v != "spo2":
                    # ACT-2: during device-reported exertion HR/RR extremes must also hold on the 30 s median
                    if v in ("hr", "rr") and t - self.recent_activity <= 120:
                        w = [b for a, b in list(self.hist[v])[-30:] if t - a < 30]
                        if len(w) < 15 or not raw_extreme(v, float(np.median(w))):
                            continue
                    safety, sreason = 3, sreason + [f"SAFE-1:{v}={x}"]
            elif qual == "suspect" and x is not None and (x == 0 or raw_extreme(v, x, self.scale)):
                if safety < 3: safety = max(safety, 2)
                sreason.append(f"SAFE-2:{v}={x} suspect ({','.join(why)})")
            elif qual == "artifact" and x is not None and raw_extreme(v, x, self.scale):
                sreason.append(f"SAFE-3:{v} confirmed artifact")
        # per-second candidate deviation + baseline feeding
        concern_any = False
        for v in V:
            qual, x, _ = q[v]
            d, z = self.base[v].z(x if qual == "valid" else None)
            c = d is not None and abs(z) >= 3 and (d <= -CAND[v] if v == "spo2" else abs(d) >= CAND[v])
            self.cand[v].append(bool(c))
            self.cand_run[v] = self.cand_run[v] + 1 if c else 0
            concern_any |= c or (qual == "valid" and (band(v, x, self.scale, self.o2) or 0) >= 3)
        concern_any |= safety >= 2
        for v in V:
            qual, x, _ = q[v]
            # PERS-B: habitual score<=2 values are eligible (simulated clinician-approved stable reference)
            elig = (qual == "valid" and (band(v, x, self.scale, self.o2) or 0) <= 2 and not self.cand[v][-1]
                    and t - self.recent_activity > 120)
            self.base[v].feed(t, x, elig, concern_any)
        if safety > self.safety[0]:
            self.safety = (safety, sreason)
        if fault or any(q[v][0] in ("missing", "artifact") for v in V):
            self.tech = self.tech or t
        self._q = q
        if (t + 1) % WINDOW_S == 0:
            return self.decide(t)
        return None

    # ---- 05 experts + 07 decision ----
    def expert(self, v, t):
        lt, lv = self.last_valid[v]
        fresh = lt is not None and t - lt <= FRESH_S
        x = lv if fresh else None
        score = band(v, x, self.scale, self.o2) if fresh else None
        d, z = self.base[v].z(x)
        h = list(self.hist[v])[-60:]
        h = [(a, b) for a, b in h if t - a <= 60]
        cov = sum(self.cand[v]) / 30
        valid_frac = sum(1 for s in self.qcount[v] if s == "valid") / max(1, len(self.qcount[v]))
        persistent = sum(self.cand[v]) >= 20 and len(self.cand[v]) == 30
        cand_now = bool(self.cand[v] and self.cand[v][-1])
        exertional = v in ("hr", "rr") and t - self.recent_activity <= 120
        concern = (None if x is None else 3 if score == 3 else 2 if score == 2 or persistent
                   else 1 if score == 1 or cand_now else 0)
        win = 60 if v == "rr" else 30                     # RR counted over a full minute (NEWS2 practice)
        h30 = [b for a, b in h if t - a < win]
        med30 = float(np.median(h30)) if len(h30) >= win // 2 else None
        # reliable score: latest value AND trailing 30 s median both score (RR/HR are rates, not 1 s snapshots)
        rel = None if score is None or med30 is None else min(score, band(v, med30, self.scale, self.o2) or 0)
        return {"domain": v, "value": x, "unit": UNIT[v], "fresh": fresh, "score": score, "median30": med30,
                "reliable_score": rel,
                "baseline": self.base[v].ref, "baseline_status": self.base[v].status, "delta": d, "z": z,
                "slope60": theil_sen([a for a, _ in h], [b for _, b in h]) if len(h) >= 24 else None,
                "slope300": theil_sen([a for a, _ in self.hist[v]], [b for _, b in self.hist[v]])
                if len(self.hist[v]) >= 120 else None,
                "candidate": cand_now, "persistent": persistent, "cand_seconds": int(sum(self.cand[v])),
                "cand_run": self.cand_run[v], "cand_frac30": cov, "valid_frac": valid_frac,
                "exertional_context": exertional, "concern": concern,
                "quality": self._q[v][0], "quality_reasons": self._q[v][2]}

    def features(self, ex):
        f = []
        for v in V:
            e = ex[v]
            f += [e["value"] if e["value"] is not None else np.nan, e["delta"] if e["delta"] is not None else np.nan,
                  e["z"] if e["z"] is not None else np.nan, e["slope60"] if e["slope60"] is not None else np.nan,
                  e["slope300"] if e["slope300"] is not None else np.nan,
                  e["score"] if e["score"] is not None else np.nan, e["cand_seconds"], e["valid_frac"]]
        sc = [ex[v]["score"] for v in V if ex[v]["score"] is not None]
        f += [float(ex["hr"]["exertional_context"]), sum(sc) if sc else np.nan, len(sc),
              sum(ex[v]["candidate"] for v in V)]
        wv = np.array(self.wv, float) if self.wv else np.full((1, 4), np.nan)    # slow-drift features (5/30 min)
        with np.errstate(all="ignore"):
            import warnings; warnings.simplefilter("ignore", RuntimeWarning)
            m5 = np.nanmedian(wv[-30:], axis=0)
            m30 = np.nanmedian(wv[-180:-150], axis=0) if len(wv) >= 180 else np.full(4, np.nan)
        for i, v in enumerate(V):
            f += [m5[i] - self.base[v].ref if self.base[v].ref is not None else np.nan, m5[i] - m30[i]]
        return f

    def decide(self, t):
        ctx, hist = self.ctx, self.ctx["history"]
        ex = {v: self.expert(v, t) for v in V}
        sc = clinical_score({v: ex[v]["value"] for v in V}, self.scale, self.o2)
        comp = sc["components"]
        rules, pri = [], 0
        safety, sreason = self.safety
        self.safety = (0, None)
        if safety == 3:
            pri, rules = 3, sreason
        elif safety == 2:
            pri, rules = 3, sreason + ["action: urgent verification (possible artifact, cannot dismiss)"]
        if pri < 3:
            relc = {v: ex[v]["reliable_score"] for v in V}
            two = sum(1 for c in relc.values() if c is not None and c >= 2)
            mod = [v for v in V if ex[v]["concern"] is not None and ex[v]["concern"] >= 2]
            corr = lambda v: [w for w in V if w != v and (ex[w]["candidate"] or (comp[w] or 0) >= 1)]
            score2 = [v for v in V if comp[v] == 2 and (relc[v] or 0) >= 2]
            transient2 = [v for v in V if comp[v] == 2 and v not in score2]
            calm = not any(ex[w]["candidate"] and not ex[w]["exertional_context"] for w in V)
            pers2 = [v for v in score2 if not (self.personalize and calm and (
                (ex[v]["z"] is not None and abs(ex[v]["z"]) < PERS_Z and abs(ex[v]["delta"]) < CAND[v])  # PERS-2
                or (ex[v]["exertional_context"] and comp["spo2"] in (0, None) and comp["temp"] in (0, None))))]  # ACT-1
            if ex["hr"]["exertional_context"] and comp["spo2"] in (0, None) and comp["temp"] in (0, None):
                two = 0; mod = [v for v in mod if v not in ("hr", "rr")]          # ACT-1 exertion
            if two >= 2 or (len(mod) >= 2 and any(ex[v]["persistent"] for v in mod)):
                pri, rules = 3, [f"CLIN-1: domains {mod or score2}"]
            elif pers2:
                pri, rules = 2, [f"CLIN-2: component score 2 ({','.join(pers2)})"]
            else:
                ctxp = [v for v in V if ex[v]["persistent"] and hist[RELEVANT[v]]
                        and not ex[v]["exertional_context"]]
                if ctxp:
                    pri, rules = 2, [f"CLIN-2: persistent deviation {v} + documented {RELEVANT[v]} history"
                                     for v in ctxp]
                else:
                    c3 = [v for v in V if ex[v]["persistent"] and not ex[v]["exertional_context"]
                          and (corr(v) or ex[v]["cand_run"] >= 60)]
                    if c3:
                        pri, rules = 2, [f"CLIN-3: persistent deviation {v}" for v in c3]
                    elif score2 or transient2 or any(c == 1 for c in comp.values()) or any(ex[v]["candidate"] for v in V):
                        pri, rules = 1, ["CLIN-4: concern, watch" + (" (score 2 within personal baseline)" if score2 else "")
                                         + (f" (transient score 2 {','.join(transient2)} not sustained 30 s)" if transient2 else "")]
                    elif sc["scored_count"] < 4:
                        pri, rules = 1, ["CLIN-6: insufficient assessment, missing " + ",".join(sc["missing_or_unscorable"])]
                    else:
                        pri, rules = 0, ["CLIN-5: all four eligible, no concerning evidence"]
        self.wv.append([np.nan if ex[v]["median30"] is None else ex[v]["median30"] for v in V])
        feats = self.features(ex)
        risk = None
        if self.model is not None:
            risk = float(self.model.predict_proba(np.array([feats]))[0, 1])
            self.ml_run = self.ml_run + 1 if ML_THRESHOLD is not None and risk >= ML_THRESHOLD else 0
            if self.ml_run >= 3 and pri < 2:
                pri, rules = 2, rules + [f"ML-1: continuous risk {risk:.2f} >= {ML_THRESHOLD:.2f} for 30 s"]
        tech = self.tech; self.tech = None
        self.state_version += 1
        verification = safety == 2 and not any(r.startswith("SAFE-1") for r in rules)
        return {"t": t, "priority": pri, "priority_label": PRI[pri], "rules": rules, "score": sc,
                "experts": ex, "risk": risk, "technical": tech is not None, "verification": verification,
                "insufficient": sc["scored_count"] < 4, "state_version": self.state_version, "features": feats,
                "policy": POLICY, "context": {k: ctx[k] for k in ("history", "facts", "beta_blocker_history", "limitations")},
                "disclaimer": "Clinical decision support only; not a diagnosis. Human review required."}


def comparator_priority(obs):
    """Fixed comparator (07 sec.6): Scale 1 bands on raw values, no quality suppression/personalization."""
    comp = [band(v, obs[v]) for v in V if obs.get(v) is not None and not math.isnan(obs[v])]
    m = max(comp) if comp else 0
    return 3 if m == 3 else 2 if m == 2 else 0


class AlertLifecycle:
    """07 sec.4: open -> acknowledged -> recovery_verification -> eligible_for_resolution -> resolved."""
    def __init__(self, auto_resolve=False):
        self.open, self.closed, self.auto, self.n = None, [], auto_resolve, 0

    def step(self, t, pri, category="clinical", evidence=None):
        ep = self.open
        if pri >= 2:
            if ep is None:
                self.n += 1
                ep = self.open = {"id": f"EP{self.n}", "category": category, "first_t": t, "last_t": t,
                                  "highest": pri, "latest": pri, "state": "open", "stable_s": 0,
                                  "acknowledged": False, "evidence": evidence or [], "escalations": []}
                return "opened"
            ep["last_t"] = t; ep["latest"] = pri; ep["stable_s"] = 0
            if ep["state"] in ("recovery_verification", "eligible_for_resolution"): ep["state"] = "open"
            if pri > ep["highest"]:
                ep["highest"] = pri; ep["escalations"].append(t)
                return "escalated"
            return None
        if ep is None:
            return None
        ep["latest"] = pri
        ep["stable_s"] = ep["stable_s"] + WINDOW_S if pri == 0 else 0     # missing/watch never counts
        if ep["stable_s"] >= 60:
            ep["state"] = "eligible_for_resolution"
            if self.auto:
                return self.resolve("simulated clinician closure at eligibility (evaluation convention)", t)
        elif ep["stable_s"] > 0:
            ep["state"] = "recovery_verification"
        return None

    def acknowledge(self, actor):
        if self.open: self.open["acknowledged"] = actor; self.open["state"] = (
            "acknowledged" if self.open["state"] == "open" else self.open["state"])

    def resolve(self, reason, t=None, actor="system"):
        ep = self.open
        if ep is None: return None
        ep.update(state="resolved", resolved_t=t, resolution_reason=reason, resolved_by=actor)
        self.closed.append(ep); self.open = None
        return "resolved"
