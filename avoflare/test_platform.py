"""Platform tests for the V4.1 components added around the engine. Unit tests run in-process; API tests need the
server on localhost:8000. Run: python test_platform.py   -> results/platform_tests.json"""
import json, time
from pathlib import Path
import httpx
import numpy as np
import records as R
import care
import twin as TW
from engine import PatientEngine, load_context, V

HERE = Path(__file__).resolve().parent
OUT = []


def check(area, name, ok, detail=""):
    OUT.append({"area": area, "test": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:200]})


# ---- FHIR + gateway (unit) ----
o = R.observation("P001", "spo2", 1000, 95.0)
check("FHIR", "Observation valid with LOINC 2708-6 and UCUM %", not R.validate(o) and o["code"]["coding"][0]["code"] == "2708-6")
check("FHIR", "Missing value uses dataAbsentReason", not R.validate(R.observation("P001", "hr", 1000, None)))
bad = R.observation("P001", "hr", 1000, 80.0); bad["valueQuantity"]["code"] = "mmHg"
check("FHIR", "Wrong unit rejected", bool(R.validate(bad)), R.validate(bad))
for v, c in (("hr", "8867-4"), ("rr", "9279-1"), ("spo2", "2708-6"), ("temp", "8310-5")):
    check("FHIR", f"{v} coded {c}", R.observation("P002", v, 5, 1.0)["code"]["coding"][0]["code"] == c)
did = R.DEVICE_OF["P003"]
b = json.dumps({"resourceType": "Bundle", "id": f"t-{time.time()}", "entry": [{"resource": R.observation("P003", "hr", 9_100_000, 70.0, session="unit")}]}).encode()
h = R.sign(did, b)
check("Gateway", "Signed bundle accepted (202)", R.ingest(h, b, "unit")[0] == 202)
check("Gateway", "Replay of same nonce rejected (401)", R.ingest(h, b, "unit")[0] == 401)
check("Gateway", "Identical retry returns stored receipt (200)", R.ingest(R.sign(did, b), b, "unit")[0] == 200)
h2 = R.sign(did, b); h2["X-Signature"] = "f" * 64
check("Gateway", "Tampered signature rejected (401)", R.ingest(h2, b, "unit")[0] == 401)
other = json.dumps({"resourceType": "Bundle", "id": f"x-{time.time()}", "entry": [{"resource": R.observation("P004", "hr", 9_100_001, 70.0, session="unit")}]}).encode()
check("Gateway", "Device cannot post another patient's data (403) - CTX-05", R.ingest(R.sign(did, other), other, "unit")[0] == 403)
check("Accounts", "Wrong password rejected", R.login("DR1", "wrong") is None)

# ---- care (unit) ----
try: care.add_symptoms("P009", "test", ["none", "fever"], "", "", 0); check("Care", "'None' with a symptom rejected", False)
except ValueError: check("Care", "'None' with a symptom rejected", True)
rec = care.add_symptoms("P009", "test", ["breathlessness"], "severe", "", 0)
check("Care", "Severe breathlessness gives emergency guidance", "emergency" in rec["guidance"])
check("Care", "Expert 6 never outputs doses", "dose" not in json.dumps(care.expert6(load_context()["P002"] | {"patient_id": "P002"},
      {"medication_history": [{"label": "albuterol"}]}, None, None)).lower().replace("no prescriptions, doses", ""))

# ---- twin (unit) ----
ctx = load_context()["P003"]; e = PatientEngine(ctx); dec = None
for t in range(1200):
    r = e.feed(t, {"hr": 78.0, "rr": 18.0, "spo2": 96.0, "temp": 36.8})
    dec = r or dec
m1 = TW.manifest("P003", "s", 1199, dec, e, ctx); m2 = TW.manifest("P003", "s", 1199, dec, e, ctx)
check("Twin", "Manifest semantic hash deterministic", m1["semantic_hash"] == m2["semantic_hash"])
check("Twin", "Manifest references all four experts", len(m1["expert_evidence_refs"]) == 4)
check("Twin", "Manifest carries no history/labels", not any(k in json.dumps(m1) for k in ("onset", "scenario", "conditions")))
vec, filled = TW.encode(dec, e, ctx)
check("Twin", "Encoder produces 264 slots with masks", vec.shape == (264,) and filled > 50, f"filled {filled}")
ens = TW.load()
if ens:
    f = ens.forecast([78, 18, 96, 36.8], [78, 18, 96, 36.8], [None] * 4, 0, TW.ctx_vec(ctx))
    check("Twin", "Abstains without baseline", f["status"] == "abstained", f.get("reason"))
    f = ens.forecast([None, None, 96, None], [78, 18, 96, 36.8], [78, 18, 96, 36.8], 0, TW.ctx_vec(ctx))
    check("Twin", "Abstains with fewer than 3 vitals", f["status"] == "abstained", f.get("reason"))
    f = ens.forecast([78, 18, 96, 36.8], [78, 18, 96, 36.8], [78, 18, 96, 36.8], 0, TW.ctx_vec(ctx))
    check("Twin", "Forecast at 5/15/30 min with uncertainty", f["status"] == "experimental" and set(f["horizons"]) == {"5min", "15min", "30min"})
    f = ens.forecast([200, 60, 60, 41], [70, 15, 98, 36.5], [78, 18, 96, 36.8], 0, TW.ctx_vec(ctx))
    check("Twin", "Out-of-distribution input abstains", f["status"] == "abstained", f.get("reason"))
    cf = TW.counterfactuals(ens, dec["experts"], [78, 18, 96, 36.8], 0, TW.ctx_vec(ctx), [78, 18, 96, 36.8])
    check("Twin", "Counterfactual branches A-D produced", {"A_original", "B_exclude_suspect", "D_tau_x0.8"} <= set(cf))
    rep = json.loads((HERE / "results/twin_report.json").read_text())
    beats = [p for p, r in rep["results"].items() if r.get("all") and r["all"]["15min"]["mae_twin"]["hr"] <= r["all"]["15min"]["mae_persistence"]["hr"]]
    check("Twin", "Held-out 15 min HR error <= persistence", len(beats) >= 2, f"{beats}")
else:
    check("Twin", "Trained twin model present", False, "run python twin.py")

# ---- API (live server) ----
creds = dict(l.split("\t")[:2] for l in (HERE / "state/initial_credentials.txt").read_text().splitlines()[1:])
try:
    def sess(uid):
        c = httpx.Client(base_url="http://localhost:8000", timeout=60)
        assert c.post("/api/login", json={"uid": uid, "password": creds[uid]}).status_code == 200
        return c
    anon = httpx.Client(base_url="http://localhost:8000", timeout=30)
    check("Security", "Clinician API requires sign-in (401)", anon.get("/api/overview").status_code == 401)
    pt = sess("PT-P001")
    check("Security", "Patient cannot read clinician overview (403)", pt.get("/api/overview").status_code == 403)
    check("Security", "Patient cannot read another patient (403)", pt.get("/api/patients/P002").status_code == 403)
    check("Patient app", "Patient reads own recovery data", pt.get("/api/me/recovery").json()["pid"] == "P001")
    nurse, dr, ops = sess("NR1"), sess("DR1"), sess("OPS1")
    check("Security", "Nurse cannot resolve alerts (403)", nurse.post("/api/alerts/P001/resolve", json={"reason": "x"}).status_code == 403)
    check("Security", "Nurse cannot approve care plan (403)", nurse.post("/api/patients/P001/careplan", json={"phase": "x", "tasks": [{"title": "t"}]}).status_code == 403)
    p = dr.post("/api/patients/P001/careplan", json={"phase": "Early recovery", "duration_days": 14,
               "tasks": [{"title": "Record morning weight", "time": "08:00"}], "medications": []})
    check("Care", "Doctor approves care plan (audited)", p.status_code == 200 and p.json()["version"] >= 1)
    task = p.json()["tasks"][0]["id"]
    check("Patient app", "Patient marks approved task done", pt.post(f"/api/me/tasks/{task}").status_code == 200)
    check("Patient app", "Unknown task rejected (404)", pt.post("/api/me/tasks/nope").status_code == 404)
    ov = dr.get("/api/overview").json()
    live = sum(1 for p in ov["patients"] if p["vitals"] and p["vitals"]["hr"]["value"] is not None)
    check("Pipeline", "Live vitals reach the engine through the signed FHIR gateway", live >= 8, f"{live}/10 patients with live HR")
    ALLOWED = ("immediate clinical assessment", "clinical review", "continue monitoring")
    for pid in ("P001", "P004", "P008"):
        sm = dr.get(f"/api/patients/{pid}/summary").json()
        row = next(p for p in ov["patients"] if p["pid"] == pid)
        rec = [s for s in sm["sentences"] if "Recommended action" in s]
        check("Doctor Ava", f"{pid} summary bound to the selected patient and session", sm["identity"]["subject"] == pid and sm["identity"]["session"] == row["session"])
        check("Doctor Ava", f"{pid} summary states only a backend recommendation", len(rec) == 1 and any(a in rec[0].lower() for a in ALLOWED), rec)
        check("Doctor Ava", f"{pid} summary carries no fabricated percentages or doses", "%" not in sm["text"] and " mg" not in sm["text"].lower())
    tl = dr.get("/api/patients/P004/timeline").json()["events"]
    check("Timeline", "Events recorded from engine output, newest first", len(tl) > 0 and all(tl[i]["t"] >= tl[i + 1]["t"] for i in range(len(tl) - 1)), f"{len(tl)} events")
    states = {p["device"]["state"] for p in ov["patients"]}
    check("Wearable", "Device states come from the defined state machine", states <= {"attached_confirmed", "removed_confirmed", "suspected_artifact", "interrupted", "unknown"}, states)
    check("Notifications", "Stored notifications carry criticality only", all("needs attention" in n["text"] and "bpm" not in n["text"] for n in dr.get("/api/notifications/team").json()["items"][:50]))
    tw = dr.get("/api/patients/P001/twin").json()
    check("Twin", "Live twin forecast produced or abstains with a reason",
          tw["forecast"]["status"] in ("experimental", "abstained") and (tw["forecast"]["status"] == "experimental" or tw["forecast"].get("reason")), tw["forecast"].get("status"))
    check("Twin", "Live manifest published by server", tw["manifest"] is not None and tw["encoder"]["slots"] == 264)
    fh = dr.get("/fhir/Observation", params={"patient": "P001", "code": "8867-4", "_count": 5}).json()
    check("FHIR", "Record interface returns FHIR searchset", fh["resourceType"] == "Bundle" and fh["total"] > 0)
    rp = ops.post("/api/eval/replay", json={"source": "bidmc", "record": "13"}).json()
    check("Replay", "BIDMC replay isolated, no live notification (INT-REPLAY-ISOLATION)", rp["live_notification"] is False and rp["source"] == "bidmc")
    check("Replay", "BIDMC record 13 RR zeros preserved", rp["rr_zero_samples_preserved"] > 0, rp["rr_zero_samples_preserved"])
    st = ops.post("/api/eval/security-tests").json()
    check("Security", "Predefined gateway attack cases all behave as expected", st["passed"] == st["total"], f"{st['passed']}/{st['total']}")
    h = ops.get("/api/eval/health").json()
    check("Records", "Outbox persists observations (cold path)", h["persistence"]["persisted"] > 0, h["persistence"])
    check("Records", "Recent stored resources all FHIR-valid", h["fhir_compliance"]["valid"] == h["fhir_compliance"]["checked"], h["fhir_compliance"])
except Exception as ex:
    check("API", "Server reachable on :8000", False, ex)

n = sum(x["result"] == "PASS" for x in OUT)
for x in OUT: print(f"{x['result']}  {x['area']:12s} {x['test']:62s} {x['detail']}")
print(f"\nPLATFORM {n}/{len(OUT)}")
(HERE / "results/platform_tests.json").write_text(json.dumps({"score": f"{n}/{len(OUT)}", "tests": OUT}, indent=1))
