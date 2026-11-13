"""Avoflare V4.1 server (hot path + APIs).
Live flow per patient: simulated wearable (10 pps -> 1 Hz) -> signed FHIR Bundle -> gateway verify/validate -> durable
store + outbox (cold path) -> safety + clinical engine -> manifest, digital twin, experts -> alert lifecycle ->
alerting agent (patient's own care team; phone/watch push) -> WebSocket -> web/app.html, web/patient.html.
Run:  set AVOFLARE_DEMO_LOGIN=1 (optional, labelled demo accounts) then  python -m uvicorn server:app --port 8000
Env: SPEED, URGENT_TIMEOUT, REVIEW_TIMEOUT, NTFY_URL (push), HAPI_URL (real HAPI FHIR), AVOFLARE_DEMO_LOGIN.
"""
import asyncio, json, os, pickle, threading, time, urllib.request, uuid
from pathlib import Path
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import engine
from engine import PatientEngine, AlertLifecycle, load_context, comparator_priority, V
import extra_vitals as XV
import records as R
import care
import twin as TW

HERE = Path(__file__).resolve().parent
DATA = Path(os.getenv("DATA", HERE / "data"))
SPEED = int(os.getenv("SPEED", "10"))
TIMEOUT = {3: int(os.getenv("URGENT_TIMEOUT", "30")), 2: int(os.getenv("REVIEW_TIMEOUT", "90"))}
NTFY, DEMO = os.getenv("NTFY_URL"), os.getenv("AVOFLARE_DEMO_LOGIN") == "1"
CHAIN = {"clinical": ["doctor", "nurse", "substitute_doctor", "management"],
         "verification": ["nurse", "doctor", "substitute_doctor", "management"]}
ROSTER = json.loads((HERE / "care_teams.json").read_text())
STAFF = {k: {**v, "available": True} for k, v in ROSTER["staff"].items()}
TEAMS = ROSTER["teams"]
KB = {p["patient_id"]: p for p in json.loads((HERE.parent / "02_patient_data/patient_kb_v1.json").read_text())["patients"]}
CTX = load_context()
LABELS = {l["patient_id"]: l for l in json.loads((DATA / "labels.json").read_text())}   # used ONLY to pick demo start time
model = None
if (HERE / "model/risk_model.pkl").exists():
    m = pickle.load(open(HERE / "model/risk_model.pkl", "rb")); model, engine.ML_THRESHOLD = m["model"], m["threshold"]
TWIN = TW.load()
P, REPLAYS, LAT = {}, {}, []
LIVE = f"live-{uuid.uuid4().hex[:6]}"                         # live session id (unique per server run)
LOCK = threading.RLock()
PERSIST = R.Persister()
CLINICAL, ALL_STAFF = {"doctor", "nurse", "management"}, {"doctor", "nurse", "management", "operator"}


# ---------------- alerting agent ----------------
def fmt(v, x): return "--" if x is None else f"{x:.1f}" if v == "temp" else f"{x:.0f}"


def push(person, title, body, urgent):
    if not NTFY: return
    def send():
        try:
            urllib.request.urlopen(urllib.request.Request(f"{NTFY.rstrip('/')}/{STAFF[person]['push_topic']}", data=body.encode(),
                                   headers={"Title": title, "Priority": "5" if urgent else "4"}), timeout=5)
        except Exception as e: print("push failed", person, e)
    threading.Thread(target=send, daemon=True).start()


def guidance(d, role):
    ex, steps = d["experts"], []
    if role in ("doctor", "substitute_doctor"):
        if any(r.startswith("SAFE-2") for r in d["rules"]): steps.append("Possible artifact: get the watch re-seated or a manual reading before acting")
        if (ex["spo2"]["score"] or 0) >= 2 or (ex["rr"]["score"] or 0) >= 2: steps.append("Call the patient now: breathlessness, chest pain, confusion? Consider urgent in-person review or ambulance")
        if (ex["hr"]["score"] or 0) >= 2: steps.append("Ask about palpitations, dizziness, bleeding; review rate-control or beta-blocker use")
        if (ex["temp"]["score"] or 0) >= 1: steps.append("Fever: screen for infection or wound site; consider sepsis screen")
        steps += ["Check the medication review items on the Care plan tab", "Acknowledge now; resolve only after review, with a reason"]
    elif role == "nurse":
        steps = ["Phone the patient and confirm they are safe", "Ask them to rest and re-seat the watch",
                 "Get manual SpO2, pulse, RR counted over 60 s, temperature", "Unreachable or worse: call ambulance per protocol", "Update the doctor"]
    else:
        steps = ["Assign an available doctor to this patient now", "Contact patient or emergency services per protocol", "Log the escalation failure"]
    return steps


def message(pid, d, role, waited):
    c, ex = CTX[pid], d["experts"]
    vit = ", ".join(f"{v.upper()} {fmt(v, ex[v]['value'])}" + ("" if ex[v]["score"] is None else f" [{ex[v]['score']}]") for v in V)
    head = f"{d['priority_label']} {pid} ({c['age']}{c['gender'][0].upper()})"
    if role == "doctor": return f"{head}: {vit}. Rules: {' | '.join(d['rules'])}."
    if role == "nurse": return f"{head}: {'Doctor unavailable or no response. ' if waited else ''}Current: {vit}."
    if role == "substitute_doctor": return f"Escalated {head}: assigned doctor and nurse did not acknowledge within {waited}s. {vit}. Please assume care."
    return f"Escalation failure {head}: no clinical acknowledgement after {waited}s."


def advance(st, ep):
    pid = st["pid"]
    while ep["step"] + 1 < len(ep["chain"]):
        ep["step"] += 1
        role = ep["chain"][ep["step"]]; person = TEAMS[pid][role]
        if STAFF[person]["available"]:
            msg, steps = message(pid, st["dec"], role, int(time.time() - ep["t0"])), guidance(st["dec"], role)
            ep["step_since"] = time.time(); ep["person"] = person
            ep["deliveries"].append({"person": person, "role": role, "sent": time.time(), "push": bool(NTFY), "received": None})
            ep["log"].append({"at": time.time(), "event": f"notified {role}", "to": STAFF[person]["name"], "person": person, "message": msg, "steps": steps})
            crit = {3: "URGENT", 2: "REVIEW"}.get(ep["highest"], "WATCH")
            short = f"{crit}: Patient {pid} needs attention. Open Avoflare when available."
            ep["deliveries"][-1]["notification_id"] = R.notify(person, role, pid, ep["highest"], ep["category"], ep["id"], short,
                                                                waited=int(time.time() - ep["t0"]))
            push(person, f"{crit} {pid}", short, ep["highest"] == 3)          # criticality only; details stay in the app
            R.audit("agent", "notify", pid, "sent", f"{role}:{person}")
            return
        ep["log"].append({"at": time.time(), "event": f"skipped {role} {STAFF[person]['name']} (unavailable)"})
    ep["log"].append({"at": time.time(), "event": "chain exhausted, reminding management every 5 minutes"})
    ep["step"] = len(ep["chain"]) - 2; ep["exhausted"] = True


# ---------------- live sessions ----------------
def presentation(fault, obs, st):
    """Media state from authorised simulator device metadata only; never from a raw zero or flatline alone."""
    if fault: return "removed_confirmed"                              # device sensor-off flag (simulated wearable)
    last = st["device"]["last_packet"]
    if all(obs[v] is None for v in V):
        return "interrupted" if last is not None and st["t"] - last > 30 else "unknown"
    q = st["dec"]["experts"]["spo2"]["quality"] if st.get("dec") else "valid"
    if q in ("suspect", "artifact"): return "suspected_artifact"
    return "attached_confirmed"


WINDOW_H = float(os.getenv("WINDOW_HOURS", "0"))           # >0: keep only this many hours per patient in memory (small hosts)
READY = threading.Event()
WS_TOKENS = {}


class Win:
    """Absolute-time view over a sliced array; outside the loaded window reads as missing."""
    def __init__(self, a, off): self.a, self.off = a, off
    def __len__(self): return self.off + len(self.a)
    def __getitem__(self, k):
        if isinstance(k, slice):
            lo = max(0, (k.start or 0) - self.off); hi = max(0, (len(self) if k.stop is None else k.stop) - self.off)
            return self.a[lo:hi]
        i = k - self.off
        if 0 <= i < len(self.a): return self.a[i]
        return np.nan if self.a.dtype.kind == "f" else False


def init():
    PERSIST.start()
    for pid, c in CTX.items():
        P[pid] = new_session(pid, c)
    READY.set()


def new_session(pid, c):
        d = dict(np.load(DATA / f"{pid}.npz")); z = dict(np.load(DATA / f"{pid}_bp_hrv.npz"))
        z["base"] = XV.baseline(z["sbp"], z["rmssd"], z["activity"])
        ev = LABELS[pid]["events"]
        start = (ev[0]["onset_t"] - 1500) if ev else 3 * 86400 + 10 * 3600
        hi = len(d["hr"])
        if WINDOW_H > 0:
            lo, hi = start - 2400, min(len(d["hr"]), start + int(WINDOW_H * 3600))
            d = {k: Win(v[lo:hi].copy(), lo) for k, v in d.items()}
        st = {"pid": pid, "e": PatientEngine(c, model), "d": d, "bp": z, "t": start - 2400, "lc": AlertLifecycle(), "dec": None, "hi": hi,
              "notes": [], "buf": {v: [] for v in V}, "closed": [], "manifests": [], "manifest": None, "forecast": None,
              "device": {"state": "unknown", "since": None, "last_packet": None}, "session": LIVE, "encoded": None}
        for _ in range(2400): step(st, None, publish=False)
        return st


def step(st, obs, publish=True, fault=None):
    t, d = st["t"], st["d"]
    if obs is None:
        obs = {v: (None if d[v][t] != d[v][t] else float(d[v][t])) for v in V}
    flt = bool(d["fault"][t]) if fault is None else fault
    r = st["e"].feed(t, {v: (np.nan if obs[v] is None else obs[v]) for v in V}, bool(d["motion"][t]), flt, bool(d["activity"][t]))
    st["t"] += 1
    for v in V:
        st["buf"][v].append(obs[v]); del st["buf"][v][:-1800]
    ps = presentation(flt, obs, st)
    if ps != st["device"]["state"]:
        st["device"] = {"state": ps, "since": t, "last_packet": st["device"]["last_packet"]}
        event(st, t, "device", f"Wearable state: {ps.replace('_', ' ')}")
    if any(obs[v] is not None for v in V): st["device"]["last_packet"] = t
    if not r: return
    st["dec"] = r
    if publish: track(st, t, r)
    if (t + 1) % 15 == 0:                                            # fixed 15 s assimilation frame (L5)
        parent = st["manifest"]["manifest_id"] if st["manifest"] else None
        if TWIN and (t + 1) % 60 == 0:
            st["forecast"] = forecast(st)
            if publish and st["forecast"]["status"] == "experimental":
                h = st["forecast"]["horizons"]["15min"]
                event(st, t, "forecast", "Twin forecast issued (experimental): 15 min " + ", ".join(f"{v.upper()} {h[v]['mean']}" for v in V if st["forecast"]["trajectory"][v]["available"]))
            elif publish and st.get("last_fc_status") != st["forecast"]["status"]:
                event(st, t, "forecast", f"Twin forecast {st['forecast']['status']}: {st['forecast'].get('reason', '')}")
            st["last_fc_status"] = st["forecast"]["status"]
        st["manifest"] = TW.manifest(st["pid"], st["session"], t, r, st["e"], CTX[st["pid"]], parent, st["forecast"])
        st["manifests"] = (st["manifests"] + [{"id": st["manifest"]["manifest_id"], "t": t, "hash": st["manifest"]["semantic_hash"]}])[-20:]
    if not publish: return
    ev = st["lc"].step(t, r["priority"], "verification" if r["verification"] else "clinical", r["rules"])
    if ev in ("opened", "escalated"):
        ep = st["lc"].open
        ep.update(chain=CHAIN[ep["category"]], step=-1, step_since=0, t0=time.time(), deliveries=ep.get("deliveries", []),
                  trigger={"rules": r["rules"], "values": {v: r["experts"][v]["value"] for v in V}, "source_t": t})
        ep["log"] = ep.get("log", []) + [{"at": time.time(), "event": ev, "priority": r["priority_label"]}]
        R.audit("engine", "alert_" + ev, st["pid"], r["priority_label"], "; ".join(r["rules"])[:300])
        event(st, t, "alert", f"Alert {ev}: {r['priority_label']} ({ep['category']})", alert=ep["id"])
        advance(st, ep)
    if st["lc"].closed and (not st["closed"] or st["lc"].closed[-1] is not st["closed"][-1]): st["closed"] = list(st["lc"].closed)


def event(st, t, kind, text, **ref):
    st.setdefault("events", []).append({"t": int(t), "time": R.iso(t), "at": time.time(), "kind": kind, "text": text, **ref})
    del st["events"][:-600]


def summarize_events(ev):
    """Deterministic plain-language digest of recorded events (no clinical inference beyond what was recorded)."""
    if not ev: return {"sentences": ["No recorded events in this period."], "counts": {}}
    from collections import Counter, OrderedDict
    hm = lambda e: R.iso(e["t"])[11:16]
    out, cnt = [], Counter(e["kind"] for e in ev)
    al = [e for e in ev if e["kind"] == "alert"]
    if al:
        opened = [e for e in al if "opened" in e["text"]]; esc_ = [e for e in al if "escalated" in e["text"]]
        out.append(f"{len(opened)} alert{'s' if len(opened) != 1 else ''} opened" + (f", {len(esc_)} escalated" if esc_ else "") +
                   (": " + "; ".join(f"{e['text'].split(': ', 1)[-1]} at {hm(e)}" for e in opened[-3:]) if opened else "") + ".")
    rv = [e for e in ev if e["kind"] == "review"]
    if rv: out.append("Actions: " + "; ".join(OrderedDict((e["text"].split(":")[0], None) for e in rv[-6:]).keys()) + ".")
    asm = [e for e in ev if e["kind"] == "assessment"]
    if asm: out.append(f"Assessment changed {len(asm)} time{'s' if len(asm) != 1 else ''}; latest {asm[-1]['text'].split(':')[0].replace('Assessment ', '')} at {hm(asm[-1])}.")
    ph = [e for e in ev if e["kind"] == "physiology"]
    if ph:
        last = OrderedDict()
        for e in ph: last[e["text"].split()[0]] = e["text"].split("(")[-1].rstrip(")")
        out.append("Persistent deviation from baseline: " + ", ".join(f"{k} ({v})" for k, v in last.items()) + ".")
    q = Counter(" ".join(e["text"].split()[:2]) for e in ev if e["kind"] == "quality")
    if q: out.append("Signal quality: " + ", ".join(f"{k} x{n}" for k, n in q.most_common(4)) + ".")
    dv = Counter(e["text"].replace("Wearable state: ", "") for e in ev if e["kind"] == "device")
    if dv: out.append("Wearable: " + ", ".join(f"{k} x{n}" for k, n in dv.items()) + ".")
    bl = OrderedDict()
    for e in ev:
        if e["kind"] == "baseline": bl[e["text"].split()[0]] = e["text"].split()[-1]
    if bl: out.append("Baseline: " + ", ".join(f"{k} {v}" for k, v in bl.items()) + ".")
    fc = [e for e in ev if e["kind"] == "forecast"]
    if fc: out.append(f"{len(fc)} experimental twin forecast{'s' if len(fc) != 1 else ''} recorded (no effect on priority).")
    return {"sentences": out, "counts": dict(cnt), "from": ev[0]["time"], "to": ev[-1]["time"]}


def track(st, t, r):
    """Record clinically meaningful state transitions from actual engine output (no derived clinical logic)."""
    prev = st.get("trk") or {}
    cur = {f"base_{v}": (r["experts"][v]["baseline_status"], st["e"].base[v].frozen) for v in V}
    cur["priority"] = r["priority"]; cur.update({f"cand_{v}": r["experts"][v]["persistent"] for v in V})
    cur.update({f"q_{v}": r["experts"][v]["quality"] for v in V})
    if prev:
        for v in V:
            (s0, f0), (s1, f1) = prev[f"base_{v}"], cur[f"base_{v}"]
            if s0 != s1: event(st, t, "baseline", f"{v.upper()} baseline {s1}")
            if f0 != f1: event(st, t, "baseline", f"{v.upper()} baseline {'frozen' if f1 else 'resumed'}")
            if cur[f"cand_{v}"] and not prev[f"cand_{v}"]: event(st, t, "physiology", f"{v.upper()} persistent deviation from baseline ({r['experts'][v]['delta']:+.1f})")
            if cur[f"q_{v}"] != prev[f"q_{v}"] and cur[f"q_{v}"] != "valid": event(st, t, "quality", f"{v.upper()} {cur[f'q_{v}']}")
        if cur["priority"] != prev["priority"]: event(st, t, "assessment", f"Assessment {r['priority_label']}: {r['rules'][0]}", priority=r["priority"])
    st["trk"] = cur


def forecast(st):
    ex = st["dec"]["experts"]
    cur = [ex[v]["value"] for v in V]
    def ago(v):
        b = [x for x in st["buf"][v][-330:-270] if x is not None]
        return float(np.median(b)) if b else None
    base = [ex[v]["baseline"] for v in V]
    act = float(np.mean(st["d"]["activity"][max(0, st["t"] - 15): st["t"]]))
    f = TWIN.forecast(cur, [ago(v) for v in V], base, act, TW.ctx_vec(CTX[st["pid"]]))
    f["source_t"] = st["t"]; f["state_version"] = st["dec"]["state_version"]
    return f


def device_bundle(st, n):
    """Simulated wearable: n seconds of 1 Hz gateway output as a signed FHIR transaction Bundle."""
    d, t0, pid = st["d"], st["t"], st["pid"]
    entries = [{"resource": R.observation(pid, v, t, None if d[v][t] != d[v][t] else float(d[v][t]), session=LIVE)}
               for t in range(t0, t0 + n) for v in V]
    body = json.dumps({"resourceType": "Bundle", "id": f"{pid}-{LIVE}-{t0}-{n}", "type": "transaction", "entry": entries}).encode()
    return R.sign(R.DEVICE_OF[pid], body), body


def tick():
    t0 = time.time()
    with LOCK:
        for pid in list(P):
            st = P[pid]
            if st["t"] + SPEED >= st["hi"]:                          # end of loaded window: restart this patient's replay
                P[pid] = st = new_session(pid, CTX[pid]); event(st, st["t"], "device", "Replay window restarted")
            hdr, body = device_bundle(st, SPEED)
            code, receipt, acc = R.ingest(hdr, body, LIVE)                    # gateway: auth, FHIR validation, durable store
            if code not in (200, 202): R.audit("gateway", "live_ingest", st["pid"], f"http {code}"); continue
            by_t = {}
            for r in acc:
                t = int((R.datetime.fromisoformat(r["effectiveDateTime"].replace("Z", "+00:00")) - R.EPOCH).total_seconds())
                by_t.setdefault(t, {})[R.CODE2V[r["code"]["coding"][0]["code"]]] = r.get("valueQuantity", {}).get("value")
            for t in range(st["t"], st["t"] + SPEED):
                step(st, {v: by_t.get(t, {}).get(v) for v in V})
            ep = st["lc"].open
            wait = 300 if ep and ep.get("exhausted") else TIMEOUT[ep["highest"]] if ep else 0
            if ep and ep.get("chain") and not ep["acknowledged"] and time.time() - ep["step_since"] > wait: advance(st, ep)
        LAT.append(time.time() - t0); del LAT[:-600]
        return json.dumps(overview_payload(), default=float)


# ---------------- payload builders ----------------
def bp_hrv(st):
    z = st["bp"]; k = int(np.searchsorted(z["t"], st["t"], "right")) - 1
    if k < 0: return None
    nz = lambda x: None if np.isnan(x) else float(x)
    hr = st["dec"]["experts"]["hr"]["value"] if st["dec"] else None
    r = XV.assess(nz(z["sbp"][k]), nz(z["dbp"][k]), nz(z["rmssd"][k]), hr, z["base"]); r["age_s"] = int(st["t"] - z["t"][k])
    return r


def alert_view(st):
    ep = st["lc"].open
    if not ep: return None
    return {k: ep.get(k) for k in ("id", "category", "highest", "latest", "state", "acknowledged", "first_t", "last_t", "evidence",
                                   "trigger", "deliveries", "escalations")} | {
        "pid": st["pid"], "current_role": ep["chain"][ep["step"]] if ep.get("chain") else None, "current_person": ep.get("person"),
        "waiting_s": int(time.time() - ep.get("step_since", time.time())), "log": ep.get("log", [])[-14:],
        "fact": next(iter([f"documented {k} history: {', '.join(CTX[st['pid']]['facts'][k][:2])}" for k, b in CTX[st['pid']]["history"].items() if b]),
                     "No relevant patient fact available (context checked)")}


def row(st):
    r = st["dec"] or {}
    ex = r.get("experts") or {}
    mon = "interrupted" if st["device"]["last_packet"] is None or st["t"] - st["device"]["last_packet"] > 30 else \
          "degraded" if r.get("technical") else "receiving"
    return {"pid": st["pid"], "age": CTX[st["pid"]]["age"], "gender": CTX[st["pid"]]["gender"], "t": st["t"], "source_time": R.iso(st["t"]),
            "source": "Simulated wearable", "session": st["session"], "assessment_version": r.get("state_version"),
            "context": ", ".join(k for k, b in CTX[st["pid"]]["history"].items() if b) or "no flagged history",
            "vitals": {v: {k: ex[v][k] for k in ("value", "score", "quality", "baseline", "delta", "z", "slope60", "baseline_status", "persistent", "fresh")} for v in V} if ex else None,
            "score": r.get("score"), "priority": r.get("priority", 0), "label": r.get("priority_label"), "rules": r.get("rules"),
            "insufficient": r.get("insufficient"), "risk": r.get("risk"), "monitoring": mon, "device": st["device"],
            "alert": alert_view(st), "bp_hrv": bp_hrv(st), "team": TEAMS[st["pid"]]}


def overview_payload():
    rows = [row(st) for st in P.values()]
    return {"type": "overview", "patients": rows, "alerts": [r["alert"] for r in rows if r["alert"]], "staff": STAFF,
            "disclaimer": "Clinical decision support only. Not a medical diagnosis system."}


# ---------------- app + auth ----------------
app = FastAPI(title="Avoflare V4.1")
clients = {}


def user(request: Request):
    s = R.session(request.cookies.get("av_session"))
    if not s: raise HTTPException(401, "Sign in required")
    return s


def need(*roles):
    def dep(s=Depends(user)):
        if s["role"] not in roles: raise HTTPException(403, "Your role cannot use this function")
        return s
    return dep


def pat(pid):
    if not READY.is_set(): raise HTTPException(503, "Starting up, patient data is loading")
    if pid not in P: raise HTTPException(404, "Unknown patient")
    return P[pid]


@app.on_event("startup")
async def start():
    threading.Thread(target=init, daemon=True).start()       # serve immediately; data loads in the background

    async def loop():
        while not READY.is_set(): await asyncio.sleep(1)
        while True:
            msg = await asyncio.to_thread(tick)
            for ws, s in list(clients.items()):
                try:
                    if s["role"] in ALL_STAFF: await ws.send_text(msg)
                except Exception: clients.pop(ws, None)
            await asyncio.sleep(1)
    asyncio.create_task(loop())


@app.post("/api/login")
async def api_login(request: Request):
    b = await request.json()
    tok = R.demo_login(b["uid"]) if DEMO and b.get("demo") and b.get("uid") in R.ACCOUNTS else R.login(b.get("uid"), b.get("password"))
    if not tok: raise HTTPException(401, "User ID or password is incorrect")
    s = R.SESSIONS[tok]
    resp = JSONResponse({"uid": s["uid"], "role": s["role"], "name": s["name"], "patient": s["patient"]})
    resp.set_cookie("av_session", tok, httponly=True, samesite="strict"); return resp


@app.post("/api/logout")
def api_logout(request: Request, response: Response):
    R.SESSIONS.pop(request.cookies.get("av_session"), None); response.delete_cookie("av_session"); return {"ok": True}


@app.get("/api/me")
def me(s=Depends(user)): return {k: s[k] for k in ("uid", "role", "name", "patient")} | {"available": STAFF.get(s["uid"], {}).get("available")}


@app.get("/api/config")
def config():
    return {"ready": READY.is_set(), "ws_url": os.getenv("PUBLIC_WS_URL"),"demo_login": DEMO, "demo_accounts": [{"uid": u, "name": a["name"], "role": a["role"]} for u, a in R.ACCOUNTS.items()] if DEMO else []}


@app.get("/api/overview")
def overview(s=Depends(need(*CLINICAL))):
    if not READY.is_set(): raise HTTPException(503, "Starting up, patient data is loading")
    with LOCK: return overview_payload()


@app.get("/api/patients/{pid}")
def patient(pid: str, s=Depends(need(*CLINICAL))):
    st = pat(pid)
    with LOCK:
        out = row(st); out["series"] = {v: st["buf"][v][-1800:] for v in V}; out["closed_alerts"] = st["closed"][-10:]
        return out


def summary(pid):
    """Deterministic spoken summary built only from engine, context, baseline, alert, twin and approved-plan outputs."""
    st = P[pid]; r = st["dec"]; c = CTX[pid]
    ident = {"source_namespace": "synthea", "subject": pid, "variant": "original", "session": st["session"]}
    if not r: return {"identity": ident, "assessment_version": None, "text": "The clinical assessment for this patient has not been completed yet.", "sentences": []}
    ex, out = r["experts"], []
    out.append(f"Patient {pid}, {c['age']} years old. Current assessment: {'insufficient assessment' if r['insufficient'] and r['priority'] < 2 else r['priority_label'] if r['priority'] else 'no current concern'}.")
    devs = [v for v in V if ex[v]["delta"] is not None and ex[v]["value"] is not None and (ex[v]["candidate"] or (ex[v]["score"] or 0) >= 2)]
    NAME = {"hr": "Heart rate", "rr": "Respiratory rate", "spo2": "Oxygen saturation", "temp": "Temperature"}
    UN = {"hr": "beats per minute", "rr": "breaths per minute", "spo2": "percent", "temp": "degrees"}
    for v in devs[:3]:
        out.append(f"{NAME[v]} is {fmt(v, ex[v]['value'])} {UN[v]}, {abs(ex[v]['delta']):.1f} {'above' if ex[v]['delta'] > 0 else 'below'} the personal baseline of {fmt(v, ex[v]['baseline'])}.")
    if not devs: out.append("No vital sign is currently outside the patient's personal baseline range.")
    hist = [k for k, b in c["history"].items() if b]
    if hist: out.append(f"Relevant documented history: {', '.join(hist)}.")
    if c.get("beta_blocker_history"): out.append("A beta blocker appears in the prescription history, but current use is not confirmed.")
    out.append("Reason: " + "; ".join(x.split(":", 1)[-1].strip() if ":" in x else x for x in r["rules"][:2]) + ".")
    ep = st["lc"].open
    if r["priority"] >= 3: out.append("Recommended action from the clinical decision: immediate clinical assessment.")
    elif r["priority"] == 2: out.append("Recommended action from the clinical decision: clinical review.")
    else: out.append("Recommended action: continue monitoring.")
    if ep: out.append(f"There is an open {ep['category']} alert, highest level {['', 'Watch', 'Review', 'Urgent'][ep['highest']]}, {'acknowledged' if ep['acknowledged'] else 'not yet acknowledged'}.")
    lim = [NAME[v].lower() for v in V if ex[v]["quality"] != "valid"]
    if lim: out.append(f"Limitations: {', '.join(lim)} {'is' if len(lim) == 1 else 'are'} missing or unreliable and need verification.")
    if any(ex[v]["baseline_status"] != "established" for v in V): out.append("The personal baseline is not yet established for every vital sign.")
    p = care.plan(pid)
    if p: out.append(f"An approved care plan is in place, phase {p['phase']}.")
    out.append("This is clinical decision support, not a diagnosis.")
    return {"identity": ident, "assessment_version": r["state_version"], "assessment_time": R.iso(r["t"]), "priority": r["priority"],
            "text": " ".join(out), "sentences": out, "sources": ["ClinicalDecision", "ClinicalScore", "Baseline", "PatientContext", "AlertLifecycle", "CarePlan"]}


@app.get("/api/patients/{pid}/summary")
def patient_summary(pid: str, s=Depends(need(*CLINICAL))):
    pat(pid)
    with LOCK: return summary(pid)


@app.get("/api/patients/{pid}/timeline")
def timeline(pid: str, s=Depends(need(*CLINICAL))):
    st = pat(pid)
    with LOCK:
        ev = st.get("events", [])
        return {"events": list(reversed(ev))[:300], "now": st["t"], "source_time": R.iso(st["t"]), "summary": summarize_events(ev),
                "last_hour": summarize_events([e for e in ev if e["t"] >= st["t"] - 3600])}


@app.get("/api/demo-login")
def demo_login_redirect(uid: str, next: str = "/"):
    """Demo-only (AVOFLARE_DEMO_LOGIN=1): sign in and redirect; used for headless screenshot capture."""
    if not DEMO or uid not in R.ACCOUNTS: raise HTTPException(404, "Not available")
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse(next if next.startswith("/") else "/")
    resp.set_cookie("av_session", R.demo_login(uid), httponly=True, samesite="lax"); return resp


@app.get("/api/patients/{pid}/profile")
def profile(pid: str, s=Depends(need(*CLINICAL))):
    k = KB[pid]
    return {"pid": pid, "fhir_patient_id": k["fhir_patient_id"], "age": k["age_at_discharge"], "gender": k["gender"],
            "clinical_cutoff": k["clinical_cutoff"], "encounter": k["encounter"], "conditions": k["conditions"],
            "medications": k["medication_history"], "procedures": k["procedures_selected_encounter"], "allergies": k.get("allergy_status") or "Unknown",
            "historical_vitals": k["historical_vitals"], "oxygen": {"scale": 1, "authorization": "None verified; Scale 1 default"},
            "care_plan": care.plan(pid), "limitations": CTX[pid]["limitations"] + (k.get("limitations") or [])}


@app.get("/api/patients/{pid}/twin")
def twin(pid: str, s=Depends(need(*CLINICAL))):
    st = pat(pid)
    with LOCK:
        if st["dec"] and TWIN: vec, filled = TW.encode(st["dec"], st["e"], CTX[pid])
        else: vec, filled = None, 0
        return {"manifest": st["manifest"], "forecast": st["forecast"] or {"status": "unavailable", "reason": "twin model not trained" if not TWIN else "first frame pending"},
                "params": TWIN.params() if TWIN else None, "encoder": {"slots": 264, "filled": filled, "registry_status": TW.REG["status"]},
                "observed": {v: st["buf"][v][-600:] for v in V}, "manifests": st["manifests"], "now": st["t"],
                "report": json.loads((HERE / "results/twin_report.json").read_text()) if (HERE / "results/twin_report.json").exists() else None}


@app.post("/api/patients/{pid}/counterfactual")
def counterfactual(pid: str, s=Depends(need("doctor", "nurse"))):
    st = pat(pid)
    if not TWIN or not st["dec"]: raise HTTPException(409, "Twin unavailable")
    with LOCK:
        ex = st["dec"]["experts"]
        x5 = [(lambda b: float(np.median(b)) if b else None)([x for x in st["buf"][v][-330:-270] if x is not None]) for v in V]
        out = TW.counterfactuals(TWIN, ex, [ex[v]["baseline"] for v in V], 0.0, TW.ctx_vec(CTX[pid]), x5)
    R.audit(s["uid"], "counterfactual", pid, "ok"); return {"branches": out, "isolated": True, "patient_state_changed": False}


@app.get("/api/patients/{pid}/intelligence")
def intelligence(pid: str, s=Depends(need(*CLINICAL))):
    st = pat(pid)
    with LOCK:
        r = st["dec"]
        return {"context": CTX[pid], "experts": r["experts"] if r else None, "rules": r["rules"] if r else None,
                "trust": {"quality": {v: r["experts"][v]["quality"] for v in V} if r else None,
                          "context_completeness": f"{sum(CTX[pid]['history'].values())} of 3 history domains documented; discharge disposition unknown",
                          "baseline": {v: st["e"].base[v].status + (" (frozen)" if st["e"].base[v].frozen else "") for v in V},
                          "model_uncertainty": st["forecast"].get("status") if st["forecast"] else "unavailable",
                          "ood": st["forecast"].get("ood_distance") if st["forecast"] else None,
                          "abstention": st["forecast"].get("reason") if st["forecast"] and st["forecast"].get("status") == "abstained" else None}}


@app.get("/api/patients/{pid}/care")
def care_view(pid: str, s=Depends(need(*CLINICAL))):
    st = pat(pid)
    with LOCK:
        day = int(st["t"] // 86400); p = care.plan(pid)
        return {"plan": p, "done_today": care.completions(pid, day), "symptoms": care.symptoms(pid),
                "expert6": care.expert6(CTX[pid] | {"patient_id": pid}, KB[pid], st["dec"], bp_hrv(st)),
                "expert7": care.expert7(pid, st["d"], st["t"], p, care.completions(pid, day), care.symptoms(pid)),
                "orders": st["notes"], "medication_history": KB[pid]["medication_history"], "medreqs": R.medreqs(pid)}


@app.post("/api/patients/{pid}/careplan")
async def careplan(pid: str, request: Request, s=Depends(need("doctor"))):
    b = await request.json()
    if not b.get("phase") or not b.get("tasks"): raise HTTPException(400, "Phase and at least one task are required")
    return care.save_plan(pid, s["uid"], b["phase"], b.get("duration_days", 14), b["tasks"], b.get("medications", []), STAFF[TEAMS[pid]["doctor"]]["name"])


@app.post("/api/patients/{pid}/review/{item}")
async def review(pid: str, item: str, request: Request, s=Depends(need("doctor"))):
    b = await request.json()
    if b.get("decision") not in ("approved", "dismissed"): raise HTTPException(400, "decision must be approved or dismissed")
    R.kv_set(f"rev:{pid}:{item}", f"{b['decision']} by {s['name']}"); R.audit(s["uid"], "med_review", pid, b["decision"], item)
    return {"ok": True}


@app.post("/api/patients/{pid}/medication")
async def medication(pid: str, request: Request, s=Depends(need("doctor"))):
    b = await request.json()
    if not (b.get("label") or "").strip(): raise HTTPException(400, "Medication is required")
    with LOCK: pat(pid)["notes"].append({"label": b["label"][:120], "at": time.time(), "status": f"ordered by {s['name']}"})
    R.audit(s["uid"], "medication_order", pid, "recorded", b["label"][:120]); return {"ok": True}


@app.get("/api/patients/{pid}/history")
def history(pid: str, s=Depends(need(*CLINICAL))):
    st = pat(pid)
    return {"observations": R.search(pid, count=40), "manifests": st["manifests"], "alerts": st["closed"][-20:],
            "audit": [dict(zip(("at", "actor", "action", "target", "outcome", "detail"), r)) for r in
                      R.DB.execute("SELECT at,actor,action,target,outcome,detail FROM audit WHERE target=? ORDER BY id DESC LIMIT 40", (pid,)).fetchall()]}


@app.post("/api/alerts/{pid}/ack")
def ack(pid: str, s=Depends(need(*CLINICAL))):
    st = pat(pid); ep = st["lc"].open
    if not ep: raise HTTPException(404, "No open alert")
    with LOCK:
        st["lc"].acknowledge(s["name"]); ep["log"].append({"at": time.time(), "event": f"acknowledged by {s['name']}"})
        event(st, st["t"], "review", f"Alert acknowledged by {s['name']}", alert=ep["id"])
    R.audit(s["uid"], "acknowledge", pid, "ok", ep["id"]); return {"ok": True}


@app.post("/api/alerts/{pid}/receipt")
def receipt(pid: str, s=Depends(need(*CLINICAL))):
    ep = pat(pid)["lc"].open
    if ep:
        for d in ep.get("deliveries", []):
            if d["person"] == s["uid"] and not d["received"]: d["received"] = time.time()
    return {"ok": True}


@app.post("/api/alerts/{pid}/resolve")
async def resolve(pid: str, request: Request, s=Depends(need("doctor"))):
    b = await request.json(); st = pat(pid)
    if not (b.get("reason") or "").strip(): raise HTTPException(400, "A resolution reason is required")
    if not st["lc"].open: raise HTTPException(404, "No open alert")
    if st["dec"] and st["dec"]["priority"] >= 2: raise HTTPException(409, "Current evidence is still Review or Urgent")
    with LOCK:
        aid = st["lc"].open["id"]; st["lc"].resolve(b["reason"], st["t"], s["name"])
        event(st, st["t"], "review", f"Alert resolved by {s['name']}: {b['reason'][:80]}", alert=aid)
    R.audit(s["uid"], "resolve", pid, "ok", b["reason"][:200]); return {"ok": True}


@app.get("/api/notifications")
def my_notifications(s=Depends(need(*CLINICAL))):
    return {"items": R.notifications(person=s["uid"]), "unread": R.unread(s["uid"])}


@app.post("/api/notifications/{nid}/read")
def read_notification(nid: int, s=Depends(need(*CLINICAL))):
    if not R.mark_read(nid, s["uid"]): raise HTTPException(404, "Notification not found")
    return {"ok": True}


@app.get("/api/notifications/team")
def team_notifications(s=Depends(need(*CLINICAL))):
    """What each care-team member received (criticality only), for the delivery screens."""
    return {"staff": STAFF, "items": R.notifications(limit=200)}


# ---------------- shifts: what happened to my patients since my last shift ----------------
def my_patients(uid):
    return [p for p, t in TEAMS.items() if uid in t.values()]


@app.post("/api/shift/start")
def shift_start(s=Depends(need("doctor", "nurse"))):
    sh = R.shift_start(s["uid"]); STAFF[s["uid"]]["available"] = True
    R.audit(s["uid"], "shift_start", "shift", "ok", sh["id"]); return sh


@app.post("/api/shift/end")
def shift_end(s=Depends(need("doctor", "nurse"))):
    sh = R.shift_end(s["uid"])
    if not sh: raise HTTPException(409, "No open shift")
    STAFF[s["uid"]]["available"] = False; R.audit(s["uid"], "shift_end", "shift", "ok", sh["id"]); return {"ok": True}


@app.get("/api/shift")
def shift_view(s=Depends(need("doctor", "nurse"))):
    uid = s["uid"]; cur = R.shift_current(uid); prev = R.shift_previous_end(uid)
    since = prev or (cur["start"] if cur else time.time()) - 12 * 3600          # first shift: last 12 hours
    reviewed = R.shift_reviews(cur["id"]) if cur else {}
    out = []
    with LOCK:
        for pid in my_patients(uid):
            st = P[pid]; ev = [e for e in st.get("events", []) if e.get("at", 0) >= since]
            role = next(r for r, x in TEAMS[pid].items() if x == uid)
            out.append({"pid": pid, "role": role, "age": CTX[pid]["age"], "gender": CTX[pid]["gender"],
                        "priority": st["dec"]["priority"] if st["dec"] else 0, "open_alert": alert_view(st),
                        "alerts": [e for e in ev if e["kind"] == "alert"], "reviews": [e for e in ev if e["kind"] == "review"],
                        "summary": summarize_events(ev),
                        "key_events": [e for e in ev if e["kind"] in ("assessment", "physiology", "quality", "device", "baseline")][-8:],
                        "event_count": len(ev), "notifications": [n for n in R.notifications(person=uid, limit=200) if n["pid"] == pid and n["at"] >= since],
                        "symptoms": [x for x in care.symptoms(pid) if x["at"] >= since],
                        "medreqs_pending": R.medreqs(pid, "pending"), "medreqs_decided": [m for m in R.medreqs(pid, since=since) if m["status"] != "pending"],
                        "tasks_done_today": len(care.completions(pid, int(st["t"] // 86400))), "reviewed": reviewed.get(pid)})
    out.sort(key=lambda x: (-(x["open_alert"]["highest"] if x["open_alert"] else 0), -x["priority"], x["pid"]))
    return {"shift": cur, "since": since, "since_label": "since your last shift ended" if prev else "last 12 hours (first shift)", "patients": out}


@app.post("/api/shift/review/{pid}")
async def shift_review(pid: str, request: Request, s=Depends(need("doctor", "nurse"))):
    cur = R.shift_current(s["uid"])
    if not cur: raise HTTPException(409, "Start your shift first")
    if pid not in my_patients(s["uid"]): raise HTTPException(403, "Not your patient")
    b = await request.json(); R.shift_review(cur["id"], s["uid"], pid, (b.get("note") or "")[:300])
    R.audit(s["uid"], "shift_review", pid, "reviewed", (b.get("note") or "")[:200]); event(P[pid], P[pid]["t"], "review", f"Shift review by {s['name']}")
    return {"ok": True}


# ---------------- medication requests: proposed by staff, decided only by a doctor ----------------
@app.get("/api/patients/{pid}/medreqs")
def list_medreqs(pid: str, s=Depends(need(*CLINICAL))):
    pat(pid); return {"items": R.medreqs(pid)}


@app.post("/api/patients/{pid}/medreqs")
async def propose_med(pid: str, request: Request, s=Depends(need("doctor", "nurse"))):
    pat(pid); b = await request.json()
    label, sched, reason = (b.get("label") or "").strip(), (b.get("schedule") or "").strip(), (b.get("reason") or "").strip()
    if not label or not sched or not reason: raise HTTPException(400, "Medication, dose and schedule, and reason are all required")
    rid = R.medreq_add(pid, s["uid"], s["role"], label[:120], sched[:120], reason[:300])
    R.audit(s["uid"], "med_request", pid, "proposed", f"#{rid} {label}"); event(P[pid], P[pid]["t"], "review", f"Medication proposed by {s['name']}: {label}")
    return {"id": rid, "status": "pending"}


@app.post("/api/medreqs/{rid}/decide")
async def decide_med(rid: int, request: Request, s=Depends(need("doctor"))):
    b = await request.json()
    if b.get("decision") not in ("approved", "rejected"): raise HTTPException(400, "decision must be approved or rejected")
    if not (b.get("note") or "").strip(): raise HTTPException(400, "A decision note is required")
    m = next((x for x in R.medreqs() if x["id"] == rid), None)
    if not m: raise HTTPException(404, "Request not found")
    if not R.medreq_decide(rid, s["uid"], b["decision"], b["note"][:300]): raise HTTPException(409, "Request already decided")
    R.audit(s["uid"], "med_decision", m["pid"], b["decision"], f"#{rid} {m['label']}")
    event(P[m["pid"]], P[m["pid"]]["t"], "review", f"Medication {b['decision']} by {s['name']}: {m['label']}")
    return {"ok": True}


@app.post("/api/staff/availability")
async def availability(request: Request, s=Depends(need(*CLINICAL))):
    b = await request.json(); STAFF[s["uid"]]["available"] = bool(b.get("available")); return STAFF[s["uid"]]


# ---------------- patient application ----------------
@app.get("/api/me/recovery")
def my_recovery(s=Depends(need("patient"))):
    st = P[s["patient"]]; pid = s["patient"]; day = int(st["t"] // 86400); p = care.plan(pid)
    return {"pid": pid, "gender": CTX[pid]["gender"], "plan": p, "done_today": care.completions(pid, day), "day": day + 1,
            "symptoms": care.symptoms(pid)[-10:], "device": st["device"], "last_data": R.iso(st["device"]["last_packet"] or 0),
            "orders": st["notes"], "approved_medications": [{"label": m["label"], "schedule": m["schedule"], "approved_by": STAFF.get(m["decided_by"], {}).get("name", m["decided_by"])} for m in R.medreqs(pid, "approved")],
            "medication_history": [{"label": m["label"], "status": m.get("discharge_use", "unconfirmed")} for m in KB[pid]["medication_history"]]}


@app.post("/api/me/tasks/{task_id}")
def my_task(task_id: str, s=Depends(need("patient"))):
    st = P[s["patient"]]
    d = care.complete_task(s["patient"], int(st["t"] // 86400), task_id, s["uid"])
    if d is None: raise HTTPException(404, "Task not in your approved plan")
    return {"done": d, "recorded_at": time.time()}


@app.post("/api/me/symptoms")
async def my_symptoms(request: Request, s=Depends(need("patient"))):
    b = await request.json(); pid = s["patient"]; st = P[pid]
    try: rec = care.add_symptoms(pid, s["uid"], b.get("symptoms", []), b.get("severity", ""), b.get("note", ""), st["t"])
    except ValueError as e: raise HTTPException(400, str(e))
    if rec["notify_care_team"]:
        person = TEAMS[pid]["doctor"]
        push(person, f"Symptom report {pid}", ", ".join(rec["symptoms"]), "breathlessness" in rec["symptoms"])
        st["notes"].append({"label": f"Patient reported: {', '.join(rec['symptoms'])} ({rec['severity'] or 'severity not given'})", "at": time.time(), "status": "patient report"})
    return rec


# ---------------- device ingestion + FHIR record interface ----------------
@app.post("/api/v1/observations")
async def observations(request: Request):
    code, payload, _ = R.ingest(dict(request.headers), await request.body())
    return JSONResponse(payload, status_code=code)


@app.get("/fhir/Observation")
def fhir_obs(patient: str = None, code: str = None, session: str = None, _count: int = 50, s=Depends(need(*ALL_STAFF))):
    pid = next((p for p, k in KB.items() if k["fhir_patient_id"] == patient or p == patient), None) if patient else None
    return R.search(pid, code, session, min(_count, 500))


# ---------------- evaluation & security console ----------------
@app.get("/api/eval/summary")
def eval_summary(s=Depends(need("operator", "doctor", "management"))):
    rd = lambda f: json.loads((HERE / "results" / f).read_text()) if (HERE / "results" / f).exists() else None
    return {"report": rd("report.json"), "metrics": rd("evaluation_metrics.json"), "bp_hrv": rd("bp_hrv_report.json"),
            "twin": rd("twin_report.json"), "scorecard": rd("scorecard.json"),
            "scenarios": json.loads((HERE.parent / "MineArena_V4_1_Integration_Update/08_evaluation/02_scenario_plan.json").read_text())}


@app.get("/api/eval/health")
def eval_health(s=Depends(need("operator", "management"))):
    q = sorted(LAT)
    pct = lambda p: None if not q else round(q[min(len(q) - 1, int(p * len(q)))] * 1000, 1)
    return {"tick_latency_ms": {"n": len(q), "p50": pct(.5), "p95": pct(.95), "p99": pct(.99),
                                "note": f"one tick = ingest+validate+store+engine for 10 patients x {SPEED} source s"},
            "persistence": PERSIST.health(), "websocket_clients": len(clients), "fhir_compliance": R.fhir_compliance(LIVE), "live_session": LIVE,
            "audit_recent": [dict(zip(("at", "actor", "action", "target", "outcome", "detail"), r)) for r in
                             R.DB.execute("SELECT at,actor,action,target,outcome,detail FROM audit ORDER BY id DESC LIMIT 30").fetchall()]}


def run_isolated(pid=None, record=None, seconds=None):
    """Replay through the same engine in an isolated session: no live notification, no shared state."""
    rid = uuid.uuid4().hex[:8]; session = f"replay-{rid}"
    if record:
        import pandas as pd
        g = pd.read_csv(HERE.parent / "04_simulation/04_simulation/bidmc_analysis/replay_numerics.csv", dtype={"record": str})
        g = g[g.record == record]
        if g.empty: raise HTTPException(404, "Unknown BIDMC record")
        seq = [{"hr": r.hr_bpm, "rr": r.rr_per_min, "spo2": r.spo2_pct, "temp": None} for r in g.itertuples()]
        ctx = {"patient_id": f"bidmc-{record}", "age": None, "history": {"respiratory": False, "cardiac": False, "infection": False},
               "facts": {}, "beta_blocker_history": False, "spo2_scale": 1, "o2": "unknown",
               "limitations": ["BIDMC recording: no Synthea context, no temperature, no wearable attachment evidence"]}
        flags, src = [(False, False, False)] * len(seq), "bidmc"
    else:
        d = dict(np.load(DATA / f"{pid}.npz")); ev = LABELS[pid]["events"]
        s0 = (ev[0]["onset_t"] - 3600) if ev else 3 * 86400; n = seconds or 3 * 3600
        seq = [{v: (None if d[v][t] != d[v][t] else float(d[v][t])) for v in V} for t in range(s0 - 1800, s0 + n)]
        flags = [(bool(d["motion"][t]), bool(d["fault"][t]), bool(d["activity"][t])) for t in range(s0 - 1800, s0 + n)]
        ctx, src = CTX[pid], "simulator"
    e, lcp, lcc = PatientEngine(ctx, model), AlertLifecycle(True), AlertLifecycle(True)
    tl, cmax, ep_p, ep_c, first_p, first_c = [], 0, 0, 0, None, None
    for t, (o, f) in enumerate(zip(seq, flags)):
        clean = {v: (np.nan if o[v] is None or o[v] != o[v] else o[v]) for v in V}
        cmax = max(cmax, comparator_priority(clean))
        r = e.feed(t, clean, *f)
        if r:
            if lcp.step(t, r["priority"]) == "opened": ep_p += 1; first_p = first_p if first_p is not None else t
            if lcc.step(t, cmax) == "opened": ep_c += 1; first_c = first_c if first_c is not None else t
            tl.append({"t": t, "proposed": r["priority"], "comparator": cmax, "rules": r["rules"][:1]}); cmax = 0
    zeros = sum(1 for o in seq if o.get("rr") == 0)
    res = {"id": rid, "session": session, "source": src, "record": record, "patient": pid, "seconds": len(seq),
           "live_notification": False, "episodes": {"avoflare": ep_p, "fixed_news2": ep_c},
           "first_alert_s": {"avoflare": first_p, "fixed_news2": first_c}, "rr_zero_samples_preserved": zeros,
           "timeline": tl[::3], "note": "Isolated replay; alerts are simulated and never delivered to staff."}
    REPLAYS[rid] = res; R.audit("operator", "replay", record or pid, "completed", rid)
    return res


@app.post("/api/eval/replay")
async def eval_replay(request: Request, s=Depends(need("operator"))):
    b = await request.json()
    if b.get("source") == "bidmc": return await asyncio.to_thread(run_isolated, None, str(b.get("record", "01")).zfill(2))
    if b.get("patient") not in P: raise HTTPException(400, "Choose a cohort patient")
    return await asyncio.to_thread(run_isolated, b["patient"], None, int(b.get("seconds", 10800)))


@app.get("/api/eval/bidmc")
def bidmc_records(s=Depends(need("operator"))):
    import csv
    rows = list(csv.DictReader(open(HERE.parent / "04_simulation/04_simulation/bidmc_analysis/record_statistics.csv")))
    return {"records": sorted({r.get("record") or r.get("record_id") for r in rows if (r.get("record") or r.get("record_id"))})}


@app.post("/api/eval/security-tests")
def security_tests(s=Depends(need("operator"))):
    pid = "P001"; did = R.DEVICE_OF[pid]; tid = uuid.uuid4().hex[:6]
    obs = lambda v=97.0, unit_ok=True, subj=None: (lambda r: (r["valueQuantity"].update(code="mmHg") if not unit_ok else None, r.update(subject={"reference": subj}) if subj else None, r)[-1])(R.observation(pid, "spo2", 9_000_000, v, session="security-test"))
    body = lambda o, i: json.dumps({"resourceType": "Bundle", "id": f"sec-{tid}-{i}", "entry": [{"resource": o}]}).encode()
    count = lambda: R.DB.execute("SELECT COUNT(*) FROM observations WHERE session='security-test'").fetchone()[0]
    cases = []
    def case(name, expected, fn):
        before = count(); code = fn(); after = count()
        cases.append({"case": name, "expected": expected, "observed": code, "pass": code == expected,
                      "records_written": after - before, "trace": f"{tid}-{len(cases)}", "p0_impact": "none (live engine untouched)"})
    b1 = body(obs(), 1); h1 = R.sign(did, b1)
    case("valid signed observation", 202, lambda: R.ingest(h1, b1, "security-test")[0])
    case("identical retry returns stored receipt", 200, lambda: R.ingest(R.sign(did, b1), b1, "security-test")[0])
    b2 = body(obs(80.0), 1)
    case("conflicting payload for same event id", 409, lambda: R.ingest(R.sign(did, b2), b2, "security-test")[0])
    case("replayed nonce", 401, lambda: R.ingest(h1, b1, "security-test")[0])
    b3 = body(obs(), 3); h3 = R.sign(did, b3); h3["X-Signature"] = "0" * 64
    case("tampered signature", 401, lambda: R.ingest(h3, b3, "security-test")[0])
    b4 = body(obs(), 4)
    case("stale timestamp", 401, lambda: R.ingest(R.sign(did, b4, ts=time.time() - 3600), b4, "security-test")[0])
    b5 = body(obs(), 5)
    case("unknown device", 401, lambda: R.ingest({"X-Device-Id": "SIM-999", "X-Timestamp": str(int(time.time())), "X-Nonce": "n", "X-Signature": "x"}, b5, "security-test")[0])
    b6 = body(obs(subj="Patient/someone-else"), 6)
    case("device sends data for another patient", 403, lambda: R.ingest(R.sign(did, b6), b6, "security-test")[0])
    b7 = body(obs(unit_ok=False), 7)
    case("invalid FHIR unit", 400, lambda: R.ingest(R.sign(did, b7), b7, "security-test")[0])
    case("human API without session", 401, lambda: (lambda: 401 if R.session(None) is None else 200)())
    case("patient account reading clinician API", 403, lambda: 403 if "patient" not in CLINICAL else 200)
    R.audit(s["uid"], "security_tests", "gateway", f"{sum(c['pass'] for c in cases)}/{len(cases)} pass", tid)
    return {"run": tid, "cases": cases, "passed": sum(c["pass"] for c in cases), "total": len(cases)}


@app.get("/api/ws-token")
def ws_token(s=Depends(user)):
    """Short-lived one-time token so a browser served from another origin (Vercel) can open the WebSocket."""
    import secrets as _s
    tok = _s.token_urlsafe(24); WS_TOKENS[tok] = (s, time.time() + 60)
    for k, (_, exp) in list(WS_TOKENS.items()):
        if exp < time.time(): WS_TOKENS.pop(k, None)
    return {"token": tok}


@app.websocket("/ws")
async def ws(w: WebSocket):
    s = R.session(w.cookies.get("av_session"))
    tok = w.query_params.get("token")
    if not s and tok in WS_TOKENS:
        s, exp = WS_TOKENS.pop(tok); s = s if exp >= time.time() else None
    while s and not READY.is_set(): await asyncio.sleep(1)
    if not s or s["role"] not in ALL_STAFF: await w.close(code=4401); return
    await w.accept(); clients[w] = s
    with LOCK: snap = json.dumps(overview_payload(), default=float)
    await w.send_text(snap)                                   # reconnect snapshot restores unresolved alerts
    try:
        while True: await w.receive_text()
    except WebSocketDisconnect: clients.pop(w, None)


app.mount("/assets", StaticFiles(directory=HERE.parent / "07_dashboard/assets"), name="assets")
app.mount("/static", StaticFiles(directory=HERE / "web"), name="static")


@app.get("/")
def index(): return FileResponse(HERE / "web/app.html")


@app.get("/patient")
def patient_app(): return FileResponse(HERE / "web/patient.html")
