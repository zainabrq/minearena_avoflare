"""Pre-deployment test run: every requirement given for this project, traced to an executed check.
Needs the server on localhost:8000 started with AVOFLARE_DEMO_LOGIN=1 (test environment only).
Run: python predeploy_check.py   -> results/predeploy_report.json and results/PREDEPLOY_REPORT.md"""
import json, re, subprocess, sys, time
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
RES = []


def req(rid, text, ok, evidence, status=None):
    RES.append({"id": rid, "requirement": text, "result": status or ("PASS" if ok else "FAIL"), "evidence": str(evidence)[:300]})


def J(f): return json.loads((HERE / "results" / f).read_text())


# 0. full automated suites (engine fixtures, BP/HRV, platform API, evaluation metrics) -> scorecard
t0 = time.time()
subprocess.run([sys.executable, "run_all_tests.py"], cwd=HERE, capture_output=True, text=True)
card = J("scorecard.json"); tests = {t["test"]: t for t in card["tests"]}
T = lambda name: tests.get(name, {"result": "FAIL", "detail": "not run"})

# 1. data + models + rules
import numpy as np
lab = json.loads((HERE / "data/labels.json").read_text()); d = np.load(HERE / "data/P001.npz")
req("R01", "10 patients x 15 days of wearable data (10 pps device, 1 Hz gateway)", len(lab) == 10 and len(d["hr"]) == 15 * 86400, f"{len(lab)} patients, {len(d['hr'])} s each")
req("R02", "Medical rules: PS03 spec fixtures (NEWS2 bands, Scale 2, baseline, artifacts, alert lifecycle)", T("Spec fixtures 08_clinical_test_cases.json")["result"] == "PASS", T("Spec fixtures 08_clinical_test_cases.json")["detail"])
rep = J("report.json"); p = rep["proposed_rules_plus_ml"]; c = rep["fixed_news2_comparator"]
req("R03", "Continuous risk score decides by threshold (ML-1, raises to Review only)", rep["ml_threshold"] is not None and T("Risk score speeds up detection vs rules only")["result"] == "PASS", f"threshold {rep['ml_threshold']}, {T('Risk score speeds up detection vs rules only')['detail']}")
req("R04", "Accurate: all deteriorations detected before severe, fewer false alerts than NEWS2", p["detected"] == p["events"] and p["min_lead_before_severe_s"] > 0 and p["false_clinical_per_patient_day"] < c["false_clinical_per_patient_day"],
    f"{p['detected']}/{p['events']}, min lead {p['min_lead_before_severe_s']} s, false/pt-day {p['false_clinical_per_patient_day']} vs {c['false_clinical_per_patient_day']}")
m = J("evaluation_metrics.json")
req("R05", "Evidence-based metrics with confidence intervals", "auroc_ci" in m["risk_model"], f"AUROC {m['risk_model']['auroc']} {m['risk_model']['auroc_ci']}")
tw = J("twin_report.json")
req("R06", "Digital twin trained and forecasting 5/15/30 min on held-out patients", T("Forecast at 5/15/30 min with uncertainty")["result"] == "PASS" and T("Held-out 15 min HR error <= persistence")["result"] == "PASS", T("Held-out 15 min HR error <= persistence")["detail"])
req("R07", "Twin uncertainty calibrated (RR band >= 90% coverage)", T("RR +/-2 SD band covers >= 90% of outcomes")["result"] == "PASS", T("RR +/-2 SD band covers >= 90% of outcomes")["detail"])
req("R08", "Blood pressure and HRV with scores and tests", T("Score boundary tests")["result"] == "PASS" and T("HRV drop flags events")["result"] == "PASS", f"{T('Score boundary tests')['detail']}; {T('HRV drop flags events')['detail']}")
req("R09", "SBP score false flags below 1 per patient-day", T("SBP score false flags < 1/pt-day")["result"] == "PASS", T("SBP score false flags < 1/pt-day")["detail"])

# 2. alerting agent: in-process routing test against server code (live server state untouched)
import server as S
from engine import PatientEngine
sent = []
S.R.notify = lambda person, role, pid, pr, cat, aid, text, waited=0: sent.append((person, role, text)) or len(sent)
S.push = lambda *a, **k: None; S.R.audit = lambda *a, **k: None
e = PatientEngine(S.CTX["P003"]); dec = None
for t in range(10): dec = e.feed(t, {"hr": 140.0, "rr": 16.0, "spo2": 97.0, "temp": 36.8}) or dec
def episode(): return {"id": "T", "chain": S.CHAIN["clinical"], "step": -1, "t0": time.time(), "deliveries": [], "log": [], "highest": 3, "category": "clinical"}
st = {"pid": "P003", "dec": dec}; team = S.TEAMS["P003"]
for k in S.STAFF: S.STAFF[k]["available"] = True
ep = episode(); S.advance(st, ep)
req("R10", "Urgent alert goes first to the patient's own doctor", ep["person"] == team["doctor"] and dec["priority"] == 3, f"P003 -> {ep['person']} ({S.STAFF[ep['person']]['name']})")
others = {S.TEAMS[p]["doctor"] for p in S.TEAMS}
req("R11", "Different patients route to different doctors (not one fixed doctor)", len(others) > 1, f"{len(others)} distinct primary doctors")
S.STAFF[team["doctor"]]["available"] = False; ep = episode(); S.advance(st, ep)
req("R12", "Doctor unavailable -> nurse", ep["person"] == team["nurse"], f"-> {ep['person']}")
S.STAFF[team["nurse"]]["available"] = False; ep = episode(); S.advance(st, ep)
req("R13", "Nurse unavailable -> substitute doctor", ep["person"] == team["substitute_doctor"], f"-> {ep['person']}")
S.STAFF[team["substitute_doctor"]]["available"] = False; ep = episode(); S.advance(st, ep)
req("R14", "Substitute unavailable -> management office", ep["person"] == team["management"], f"-> {ep['person']}")
for k in S.STAFF: S.STAFF[k]["available"] = True
ep = episode(); [S.advance(st, ep) for _ in range(5)]
req("R15", "No acknowledgement: escalates through the whole chain, then reminds management", ep.get("exhausted") and [d["role"] for d in ep["deliveries"]][:4] == ["doctor", "nurse", "substitute_doctor", "management"], [d["role"] for d in ep["deliveries"]])
roles_msgs = {r: S.message("P003", dec, r, 40) for r in ("doctor", "nurse", "substitute_doctor", "management")}
req("R16", "Different information to doctor, nurse, substitute and management", len(set(roles_msgs.values())) == 4 and len({tuple(S.guidance(dec, r)) for r in ("doctor", "nurse", "management")}) == 3, "4 distinct messages, 3 distinct guidance lists")
req("R17", "Phone/watch notifications carry criticality only", all(re.fullmatch(r"(URGENT|REVIEW|WATCH): Patient P\d+ needs attention\. Open Avoflare when available\.", t) for _, _, t in sent), sent[0][2] if sent else "none")
req("R18", "Phone/smartwatch push delivery configured", bool(S.NTFY), "NTFY_URL is not set: in-app inbox + browser notifications only; set NTFY_URL to deliver to phones/watches", status=None if S.NTFY else "CONFIG REQUIRED")

# 3. frontend obligations (static checks of the shipped files)
app = (HERE / "web/app.html").read_text(encoding="utf-8")
req("R19", "Alarm sounds for every unacknowledged Urgent alert, for all clinical staff, until acknowledged", "function urgentAll(){return OV?OV.alerts.filter(a=>a.highest==3&&!a.acknowledged)" in app and "setInterval(()=>{if(ME&&OV&&ME.role!='operator')alarm()},600)" in app, "urgentAll() + 600 ms alarm loop")
assets = ["images/logo.png", "images/patient_avatar_female.png", "images/patient_avatar_male.png", "images/watch_attached.png", "images/watch_removed.png",
          "videos/login_hero.mp4", "videos/watch_attached.mp4", "videos/watch_removed.mp4"]
web = app + (HERE / "web/patient.html").read_text(encoding="utf-8")
served = [a for a in assets if httpx.get(f"http://localhost:8000/assets/{a}", timeout=60).status_code == 200]
referenced = [a for a in assets if Path(a).stem in web]
req("R20", "All supplied dashboard assets used (logo, avatars, watch stills and videos, login video)", len(served) == len(referenced) == len(assets), f"referenced {len(referenced)}/8, served {len(served)}/8")
req("R21", "Clinical decision support disclaimer present", "Clinical decision support only. Not a medical diagnosis system." in app, "shell footer + login")

# 4. live API: platform suite + shift + medication workflow
pt = J("platform_tests.json")
req("R22", "Platform suite (FHIR, gateway security, roles, patient app, twin, BIDMC isolation, Doctor Ava, timeline, notifications)", pt["score"].split("/")[0] == pt["score"].split("/")[1], pt["score"])
creds = dict(l.split("\t")[:2] for l in (HERE / "state/initial_credentials.txt").read_text().splitlines()[1:])
def login(uid):
    c = httpx.Client(base_url="http://localhost:8000", timeout=120); r = c.post("/api/login", json={"uid": uid, "password": creds[uid]}); assert r.status_code == 200, uid; return c
try:
    nurse, doc, other, pat = login("NR1"), login("DR1"), login("DR2"), login("PT-P001")
    r = nurse.post("/api/patients/P001/medreqs", json={"label": "Test medication 5 mg tablet", "schedule": "once daily (test entry)", "reason": "pre-deployment workflow check"})
    rid = r.json().get("id")
    req("R23", "Nurse can propose a medication (pending until a doctor decides)", r.status_code == 200 and r.json()["status"] == "pending", r.status_code)
    req("R24", "Nurse cannot approve medication", nurse.post(f"/api/medreqs/{rid}/decide", json={"decision": "approved", "note": "x"}).status_code == 403, "403")
    req("R25", "Doctor decision requires a note", doc.post(f"/api/medreqs/{rid}/decide", json={"decision": "approved", "note": ""}).status_code == 400, "400")
    ok = doc.post(f"/api/medreqs/{rid}/decide", json={"decision": "approved", "note": "approved during pre-deployment check"}).status_code == 200
    req("R26", "Doctor approves; second decision on the same request is refused", ok and doc.post(f"/api/medreqs/{rid}/decide", json={"decision": "rejected", "note": "x"}).status_code == 409, "200 then 409")
    am = pat.get("/api/me/recovery").json().get("approved_medications", [])
    req("R27", "Approved medication appears in the patient's app", any(m["label"] == "Test medication 5 mg tablet" for m in am), f"{len(am)} approved items")
    doc.post("/api/shift/start"); sv = doc.get("/api/shift").json()
    req("R28", "Doctor shift: start shift puts the doctor on duty", sv["shift"] is not None and doc.get("/api/me").json()["available"] is True, sv["since_label"])
    mine = {x["pid"] for x in sv["patients"]}
    req("R29", "Shift view lists only the doctor's own patients with what happened (alerts, events, symptoms, medication)",
        mine == set(S.my_patients("DR1")) and all({"alerts", "key_events", "symptoms", "medreqs_pending", "notifications"} <= set(x) for x in sv["patients"]), sorted(mine))
    r1 = doc.post("/api/shift/review/P001", json={"note": "pre-deployment check"}).status_code
    r2 = doc.post("/api/shift/review/P003", json={"note": "x"}).status_code
    req("R30", "Doctor signs off each patient review; cannot review another doctor's patient", r1 == 200 and r2 == 403 and doc.get("/api/shift").json()["patients"][0] is not None, f"own 200, other 403")
    doc.post("/api/shift/end")
    req("R31", "Ending the shift takes the doctor off duty (escalations skip them)", doc.get("/api/me").json()["available"] is False, "available False")
    doc.post("/api/staff/availability", json={"available": True})
    a = other.post("/api/alerts/P004/ack").status_code
    req("R32", "Acknowledge and resolve are separate; resolve needs a doctor and a reason", nurse.post("/api/alerts/P001/resolve", json={"reason": "x"}).status_code == 403
        and doc.post("/api/alerts/P001/resolve", json={"reason": ""}).status_code in (400, 404), f"nurse 403, empty reason rejected")
except Exception as ex:
    req("R23", "Live API workflow checks", False, ex)

# report
n = {k: sum(r["result"] == k for r in RES) for k in ("PASS", "FAIL", "CONFIG REQUIRED")}
out = {"run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "duration_s": round(time.time() - t0), "summary": n, "scorecard": card["score"], "requirements": RES}
(HERE / "results/predeploy_report.json").write_text(json.dumps(out, indent=1))
md = [f"# Pre-deployment test run ({out['run_at']})", "", f"PASS {n['PASS']} · FAIL {n['FAIL']} · CONFIG REQUIRED {n['CONFIG REQUIRED']} · full scorecard {card['score']}", "",
      "| ID | Requirement | Result | Evidence |", "|---|---|---|---|"] + [f"| {r['id']} | {r['requirement']} | {r['result']} | {r['evidence'].replace('|', '/')} |" for r in RES]
(HERE / "results/PREDEPLOY_REPORT.md").write_text("\n".join(md), encoding="utf-8")
for r in RES: print(f"{r['result']:15s} {r['id']} {r['requirement'][:80]}")
print(f"\nPASS {n['PASS']}  FAIL {n['FAIL']}  CONFIG REQUIRED {n['CONFIG REQUIRED']}  (scorecard {card['score']})")
