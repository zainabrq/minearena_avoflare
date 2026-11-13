"""Layer 2 gateway security + cold path: FHIR R4 Observation encoding/validation, HMAC-signed device ingestion with
replay protection, durable SQLite store (observations, outbox, audit, care data) standing in for PostgreSQL/HAPI,
optional forwarding to a real HAPI FHIR server (HAPI_URL), and human accounts/sessions.
Secrets (device keys, password hashes) live in avoflare/state/, generated on first run, never in code."""
import hashlib, hmac, json, os, secrets, sqlite3, threading, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATE = HERE / "state"; STATE.mkdir(exist_ok=True)
LOINC = {"hr": ("8867-4", "Heart rate", "/min"), "rr": ("9279-1", "Respiratory rate", "/min"),
         "spo2": ("2708-6", "Oxygen saturation in Arterial blood", "%"), "temp": ("8310-5", "Body temperature", "Cel")}
CODE2V = {c[0]: v for v, c in LOINC.items()}
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)             # simulated source clock origin (source time != wall time)
MAPPING = {p["patient_id"]: p for p in json.loads((ROOT / "MineArena_V4_1_Integration_Update/02_patient_data/patient_device_mapping_v1.json").read_text())["patients"]}
LOCK = threading.RLock()
DB = sqlite3.connect(STATE / "avoflare.db", check_same_thread=False, isolation_level=None)
DB.execute("PRAGMA journal_mode=WAL")
DB.executescript("""
CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, event_id TEXT, pid TEXT, session TEXT, code TEXT, effective TEXT,
  source_t INTEGER, value REAL, resource TEXT, payload_hash TEXT, status TEXT, created REAL);
CREATE INDEX IF NOT EXISTS obs_pid ON observations(pid, code, source_t);
CREATE INDEX IF NOT EXISTS obs_session ON observations(session);
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY AUTOINCREMENT, person TEXT, start REAL, end REAL);
CREATE TABLE IF NOT EXISTS medreqs(id INTEGER PRIMARY KEY AUTOINCREMENT, pid TEXT, at REAL, proposed_by TEXT, role TEXT, label TEXT,
  schedule TEXT, reason TEXT, status TEXT, decided_by TEXT, decided_at REAL, note TEXT);
CREATE TABLE IF NOT EXISTS shift_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, shift_id INTEGER, person TEXT, pid TEXT, at REAL, note TEXT);
CREATE TABLE IF NOT EXISTS receipts(event_id TEXT PRIMARY KEY, payload_hash TEXT, receipt TEXT);
CREATE TABLE IF NOT EXISTS outbox(obs_id TEXT PRIMARY KEY, attempts INTEGER, state TEXT, last_error TEXT);
CREATE TABLE IF NOT EXISTS nonces(nonce TEXT PRIMARY KEY, at REAL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, actor TEXT, action TEXT, target TEXT, outcome TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, person TEXT, role TEXT, pid TEXT, priority INTEGER,
  category TEXT, alert_id TEXT, text TEXT, waited_s INTEGER, read_at REAL);
""")


def audit(actor, action, target, outcome, detail=""):
    with LOCK: DB.execute("INSERT INTO audit(at,actor,action,target,outcome,detail) VALUES(?,?,?,?,?,?)",
                          (time.time(), actor, action, target, outcome, str(detail)[:500]))


def notify(person, role, pid, priority, category, alert_id, text, waited=0):
    with LOCK:
        return DB.execute("INSERT INTO notifications(at,person,role,pid,priority,category,alert_id,text,waited_s) VALUES(?,?,?,?,?,?,?,?,?)",
                          (time.time(), person, role, pid, priority, category, alert_id, text, waited)).lastrowid


def notifications(person=None, limit=50):
    q, a = "SELECT id,at,person,role,pid,priority,category,alert_id,text,waited_s,read_at FROM notifications", []
    if person: q += " WHERE person=?"; a.append(person)
    rows = DB.execute(q + " ORDER BY id DESC LIMIT ?", a + [limit]).fetchall()
    return [dict(zip(("id", "at", "person", "role", "pid", "priority", "category", "alert_id", "text", "waited_s", "read_at"), x)) for x in rows]


def unread(person):
    return DB.execute("SELECT COUNT(*) FROM notifications WHERE person=? AND read_at IS NULL", (person,)).fetchone()[0]


def mark_read(nid, person):
    with LOCK:
        return DB.execute("UPDATE notifications SET read_at=? WHERE id=? AND person=?", (time.time(), nid, person)).rowcount


def shift_current(person):
    r = DB.execute("SELECT id,person,start,end FROM shifts WHERE person=? AND end IS NULL ORDER BY id DESC LIMIT 1", (person,)).fetchone()
    return dict(zip(("id", "person", "start", "end"), r)) if r else None


def shift_previous_end(person):
    r = DB.execute("SELECT MAX(end) FROM shifts WHERE person=? AND end IS NOT NULL", (person,)).fetchone()
    return r[0]


def shift_start(person):
    cur = shift_current(person)
    if cur: return cur
    with LOCK: DB.execute("INSERT INTO shifts(person,start) VALUES(?,?)", (person, time.time()))
    return shift_current(person)


def shift_end(person):
    cur = shift_current(person)
    if cur:
        with LOCK: DB.execute("UPDATE shifts SET end=? WHERE id=?", (time.time(), cur["id"]))
    return cur


def shift_reviews(shift_id):
    return {r[0]: {"at": r[1], "note": r[2]} for r in DB.execute("SELECT pid,at,note FROM shift_reviews WHERE shift_id=?", (shift_id,)).fetchall()}


def shift_review(shift_id, person, pid, note):
    with LOCK: DB.execute("INSERT INTO shift_reviews(shift_id,person,pid,at,note) VALUES(?,?,?,?,?)", (shift_id, person, pid, time.time(), note))


MR = ("id", "pid", "at", "proposed_by", "role", "label", "schedule", "reason", "status", "decided_by", "decided_at", "note")


def medreq_add(pid, person, role, label, schedule, reason):
    with LOCK:
        return DB.execute("INSERT INTO medreqs(pid,at,proposed_by,role,label,schedule,reason,status) VALUES(?,?,?,?,?,?,?,'pending')",
                          (pid, time.time(), person, role, label, schedule, reason)).lastrowid


def medreqs(pid=None, status=None, since=None):
    q, a = "SELECT " + ",".join(MR) + " FROM medreqs WHERE 1=1", []
    if pid: q += " AND pid=?"; a.append(pid)
    if status: q += " AND status=?"; a.append(status)
    if since: q += " AND (at>=? OR decided_at>=?)"; a += [since, since]
    return [dict(zip(MR, r)) for r in DB.execute(q + " ORDER BY id DESC", a).fetchall()]


def medreq_decide(rid, person, decision, note):
    with LOCK:
        return DB.execute("UPDATE medreqs SET status=?, decided_by=?, decided_at=?, note=? WHERE id=? AND status='pending'",
                          (decision, person, time.time(), note, rid)).rowcount


def audit_since(target, since, prefix=""):
    rows = DB.execute("SELECT at,actor,action,outcome,detail FROM audit WHERE target=? AND at>=? AND action LIKE ? ORDER BY id",
                      (target, since, prefix + "%")).fetchall()
    return [dict(zip(("at", "actor", "action", "outcome", "detail"), r)) for r in rows]


def kv_get(k, default=None):
    r = DB.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else default


def kv_set(k, v):
    with LOCK: DB.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (k, json.dumps(v)))


# ---------------- device keys + signing ----------------
SEED = os.getenv("AVOFLARE_ACCOUNT_SEED")          # deployments with ephemeral disks: derive stable secrets from one env secret


def derived(kind, name, n=32):
    return hmac.new(SEED.encode(), f"{kind}:{name}".encode(), hashlib.sha256).hexdigest()[:n]


def _devices():
    if SEED:
        return {p["proposed_device_id"]: {"patient_id": pid, "secret": derived("device", p["proposed_device_id"], 64)}
                for pid, p in MAPPING.items() if p.get("proposed_device_id")}
    f = STATE / "devices.json"
    if not f.exists():
        f.write_text(json.dumps({p["proposed_device_id"]: {"patient_id": pid, "secret": secrets.token_hex(32)}
                                 for pid, p in MAPPING.items() if p.get("proposed_device_id")}, indent=1))
    return json.loads(f.read_text())


DEVICES = _devices()
DEVICE_OF = {v["patient_id"]: k for k, v in DEVICES.items()}


def sign(device_id, body: bytes, ts=None, nonce=None):
    ts = str(int(ts or time.time())); nonce = nonce or secrets.token_hex(12)
    msg = f"{device_id}\n{ts}\n{nonce}\n{hashlib.sha256(body).hexdigest()}".encode()
    return {"X-Device-Id": device_id, "X-Timestamp": ts, "X-Nonce": nonce,
            "X-Signature": hmac.new(bytes.fromhex(DEVICES[device_id]["secret"]), msg, hashlib.sha256).hexdigest()}


def verify(headers, body: bytes):
    """Returns (device_id, error). Checks known device, timestamp window, nonce reuse, HMAC."""
    did, ts, nonce, sig = (headers.get(k) for k in ("x-device-id", "x-timestamp", "x-nonce", "x-signature"))
    if not all((did, ts, nonce, sig)) or did not in DEVICES: return None, "unknown or missing device credentials"
    if abs(time.time() - int(ts)) > 300: return None, "timestamp outside 300 s window"
    msg = f"{did}\n{ts}\n{nonce}\n{hashlib.sha256(body).hexdigest()}".encode()
    if not hmac.compare_digest(hmac.new(bytes.fromhex(DEVICES[did]["secret"]), msg, hashlib.sha256).hexdigest(), sig):
        return None, "invalid signature"
    with LOCK:
        if DB.execute("SELECT 1 FROM nonces WHERE nonce=?", (nonce,)).fetchone(): return None, "replayed nonce"
        DB.execute("INSERT INTO nonces VALUES(?,?)", (nonce, time.time()))
    return did, None


# ---------------- FHIR ----------------
def iso(source_t):
    return (EPOCH + timedelta(seconds=int(source_t))).isoformat().replace("+00:00", "Z")


def observation(pid, vital, source_t, value, session="live", quality="valid"):
    code, display, unit = LOINC[vital]
    fid = MAPPING[pid]["fhir_patient_id"] if pid in MAPPING else pid
    r = {"resourceType": "Observation", "id": f"{pid}-{session}-{vital}-{int(source_t)}", "status": "final" if quality == "valid" else "preliminary",
         "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
         "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": display}]},
         "subject": {"reference": f"Patient/{fid}"}, "device": {"reference": f"Device/{DEVICE_OF.get(pid, 'replay')}"},
         "effectiveDateTime": iso(source_t),
         "meta": {"tag": [{"system": "urn:avoflare:quality", "code": quality}, {"system": "urn:avoflare:session", "code": session}]}}
    if value is None or value != value:
        r["dataAbsentReason"] = {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason", "code": "unknown"}]}
    else:
        r["valueQuantity"] = {"value": round(float(value), 2), "unit": unit, "system": "http://unitsofmeasure.org", "code": unit}
    return r


def validate(r):
    e = []
    if r.get("resourceType") != "Observation": e.append("resourceType must be Observation")
    if r.get("status") not in ("final", "preliminary", "amended"): e.append("invalid status")
    cod = (r.get("code", {}).get("coding") or [{}])[0]
    if cod.get("system") != "http://loinc.org" or cod.get("code") not in CODE2V: e.append("code must be LOINC 8867-4/9279-1/2708-6/8310-5")
    if not str(r.get("subject", {}).get("reference", "")).startswith("Patient/"): e.append("subject must reference Patient")
    try: datetime.fromisoformat(r.get("effectiveDateTime", "").replace("Z", "+00:00"))
    except Exception: e.append("effectiveDateTime missing or invalid")
    vq, dar = r.get("valueQuantity"), r.get("dataAbsentReason")
    if bool(vq) == bool(dar): e.append("exactly one of valueQuantity or dataAbsentReason required")
    if vq and cod.get("code") in CODE2V and vq.get("code") != LOINC[CODE2V[cod["code"]]][2]: e.append("unit does not match canonical UCUM unit")
    if vq and not isinstance(vq.get("value"), (int, float)): e.append("valueQuantity.value must be numeric")
    return e


def outcome(errors, code="invalid"):
    return {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": code, "diagnostics": x} for x in errors]}


def ingest(headers, body: bytes, session="live"):
    """POST /api/v1/observations. Returns (http_status, payload, accepted_observations)."""
    did, err = verify({k.lower(): v for k, v in headers.items()}, body)
    if err:
        audit(headers.get("X-Device-Id", "?"), "ingest", "observations", "rejected", err)
        return 401, outcome([err], "security"), []
    try: bundle = json.loads(body)
    except Exception: return 400, outcome(["body is not JSON"]), []
    entries = [x["resource"] for x in bundle.get("entry", [])] if bundle.get("resourceType") == "Bundle" else [bundle]
    pid = DEVICES[did]["patient_id"]; fid = MAPPING[pid]["fhir_patient_id"]
    errs, accepted = [], []
    for r in entries:
        ve = validate(r)
        if r.get("subject", {}).get("reference") != f"Patient/{fid}": ve.append("device not authorised for this patient")
        if ve: errs += [f"{r.get('id')}: {x}" for x in ve]
        else: accepted.append(r)
    if errs and any("not authorised" in x for x in errs):
        audit(did, "ingest", pid, "rejected", "patient mapping mismatch"); return 403, outcome(errs, "forbidden"), []
    if errs:
        audit(did, "ingest", pid, "rejected", errs[:3]); return 400, outcome(errs), []
    event_id = bundle.get("id") or hashlib.sha256(body).hexdigest()[:20]
    ph = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()
    with LOCK:
        prev = DB.execute("SELECT payload_hash, receipt FROM receipts WHERE event_id=?", (event_id,)).fetchone()
        if prev:
            if prev[0] == ph: return 200, json.loads(prev[1]), []                      # identical retry: stored receipt
            audit(did, "ingest", pid, "conflict", event_id); return 409, outcome(["conflicting payload for event id"], "conflict"), []
        rows = []
        for r in accepted:
            v = CODE2V[r["code"]["coding"][0]["code"]]
            t = int((datetime.fromisoformat(r["effectiveDateTime"].replace("Z", "+00:00")) - EPOCH).total_seconds())
            rows.append((r["id"], event_id, pid, session, LOINC[v][0], r["effectiveDateTime"], t,
                         r.get("valueQuantity", {}).get("value"), json.dumps(r), ph, "accepted", time.time()))
        DB.execute("BEGIN")
        DB.executemany("INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        DB.executemany("INSERT OR IGNORE INTO outbox VALUES(?,0,'pending',NULL)", [(r[0],) for r in rows])
        receipt = {"event_id": event_id, "status": "accepted", "processing": "queued", "count": len(rows)}
        DB.execute("INSERT INTO receipts VALUES(?,?,?)", (event_id, ph, json.dumps(receipt)))
        DB.execute("COMMIT")
    return 202, receipt, accepted


class Persister(threading.Thread):
    """Outbox worker: forwards to HAPI_URL if configured (circuit breaker), otherwise commits to the local FHIR store.
    Asynchronous: never blocks the safety path."""
    def __init__(self):
        super().__init__(daemon=True); self.hapi = os.getenv("HAPI_URL"); self.fail = 0; self.open_until = 0; self.stats = {"persisted_this_run": 0, "failed_this_run": 0}

    def run(self):
        while True:
            rows = DB.execute("SELECT o.obs_id, r.resource FROM outbox o JOIN observations r ON r.id=o.obs_id WHERE o.state='pending' LIMIT 500").fetchall()
            if not rows: time.sleep(1); continue
            if self.hapi and time.time() < self.open_until: time.sleep(1); continue
            done, failed = [], []
            for oid, res in rows:
                if self.hapi:
                    try:
                        req = urllib.request.Request(f"{self.hapi.rstrip('/')}/Observation/{oid}", data=res.encode(), method="PUT",
                                                     headers={"Content-Type": "application/fhir+json"})
                        urllib.request.urlopen(req, timeout=5); done.append(oid); self.fail = 0
                    except Exception as ex:
                        failed.append((str(ex)[:200], oid)); self.fail += 1
                        if self.fail >= 3: self.open_until = time.time() + 60; break
                else:
                    done.append(oid)
            with LOCK:
                DB.execute("BEGIN")
                DB.executemany("UPDATE outbox SET state='persisted' WHERE obs_id=?", [(o,) for o in done])
                DB.executemany("UPDATE observations SET status=? WHERE id=?", [("stored_hapi" if self.hapi else "stored_local", o) for o in done])
                DB.executemany("UPDATE outbox SET attempts=attempts+1, last_error=? WHERE obs_id=?", failed)
                DB.execute("COMMIT")
            self.stats["persisted_this_run"] += len(done); self.stats["failed_this_run"] += len(failed)

    def health(self):
        q = dict(DB.execute("SELECT state, COUNT(*) FROM outbox GROUP BY state").fetchall())
        oldest = DB.execute("SELECT MIN(created) FROM observations WHERE status='accepted'").fetchone()[0]
        return {"target": "HAPI " + self.hapi if self.hapi else "local FHIR store (HAPI_URL not set)",
                "circuit": "open" if time.time() < self.open_until else "closed", "pending": q.get("pending", 0),
                "persisted": q.get("persisted", 0), "oldest_pending_age_s": None if not oldest else round(time.time() - oldest, 1), **self.stats}


def search(pid=None, code=None, session=None, count=50):
    q, a = "SELECT resource, status FROM observations WHERE 1=1", []
    if pid: q += " AND pid=?"; a.append(pid)
    if code: q += " AND code=?"; a.append(code)
    if session: q += " AND session=?"; a.append(session)
    rows = DB.execute(q + " ORDER BY source_t DESC LIMIT ?", a + [int(count)]).fetchall()
    return {"resourceType": "Bundle", "type": "searchset", "total": len(rows),
            "entry": [{"resource": json.loads(r), "search": {"mode": "match"}, "response": {"status": s}} for r, s in rows]}


def fhir_compliance(session="live", sample=2000):
    rows = DB.execute("SELECT resource FROM observations WHERE session=? ORDER BY rowid DESC LIMIT ?", (session, sample)).fetchall()
    bad = sum(1 for (r,) in rows if validate(json.loads(r)))
    return {"checked": len(rows), "valid": len(rows) - bad}


# ---------------- human accounts + sessions ----------------
def _hash(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(os.getenv("PBKDF2_ITERS", "200000"))).hex()


def accounts():
    f = STATE / "accounts.json"
    if SEED and not f.exists():                                   # stable passwords from the seed (shown once by deploy tooling)
        teams = json.loads((HERE / "care_teams.json").read_text())
        people = {k: {"name": s["name"], "role": s["role"], "patient": None} for k, s in teams["staff"].items()}
        people.update({f"PT-{p}": {"name": f"Patient {p}", "role": "patient", "patient": p} for p in teams["teams"]})
        people["OPS1"] = {"name": "Evaluation operator", "role": "operator", "patient": None}
        for uid, p in people.items():
            salt = derived("salt", uid, 32); p.update(salt=salt, hash=_hash(derived("pw", uid, 14), salt))
        f.write_text(json.dumps(people, indent=1))
    if not f.exists():
        teams = json.loads((HERE / "care_teams.json").read_text())
        people = {k: {"name": s["name"], "role": s["role"], "patient": None} for k, s in teams["staff"].items()}
        people.update({f"PT-{p}": {"name": f"Patient {p}", "role": "patient", "patient": p} for p in teams["teams"]})
        people["OPS1"] = {"name": "Evaluation operator", "role": "operator", "patient": None}
        creds = {}
        for uid, p in people.items():
            pw = secrets.token_urlsafe(9); salt = secrets.token_hex(16)
            p.update(salt=salt, hash=_hash(pw, salt)); creds[uid] = pw
        f.write_text(json.dumps(people, indent=1))
        (STATE / "initial_credentials.txt").write_text("Generated local credentials (change before any shared use)\n" +
                                                     "\n".join(f"{u}\t{pw}\t{people[u]['role']}" for u, pw in creds.items()))
    return json.loads(f.read_text())


ACCOUNTS = accounts()
SESSIONS = {}


def login(uid, pw):
    a = ACCOUNTS.get(uid)
    if not a or not hmac.compare_digest(_hash(pw or "", a["salt"]), a["hash"]):
        audit(uid or "?", "login", "session", "rejected"); return None
    tok = secrets.token_urlsafe(32)
    SESSIONS[tok] = {"uid": uid, "role": a["role"], "name": a["name"], "patient": a["patient"], "at": time.time()}
    audit(uid, "login", "session", "ok"); return tok


def demo_login(uid):
    a = ACCOUNTS[uid]; tok = secrets.token_urlsafe(32)
    SESSIONS[tok] = {"uid": uid, "role": a["role"], "name": a["name"], "patient": a["patient"], "at": time.time(), "demo": True}
    audit(uid, "login", "session", "ok", "demo login (AVOFLARE_DEMO_LOGIN=1)"); return tok


def session(tok):
    s = SESSIONS.get(tok or "")
    return s if s and time.time() - s["at"] < 12 * 3600 else None
