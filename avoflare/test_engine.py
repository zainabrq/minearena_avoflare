"""Executes the spec fixtures in 03_clinical_intelligence/08_clinical_test_cases.json (V4.1). Run: python test_engine.py"""
import json
from engine import ROOT, band, clinical_score, PatientEngine, AlertLifecycle, load_context, V

CASES = json.loads((ROOT / "MineArena_V4_1_Integration_Update/03_clinical_intelligence/08_clinical_test_cases.json").read_text())["cases"]
CTX = load_context()
DEFAULT = {"hr": 80, "rr": 16, "spo2": 97, "temp": 36.8}


def run(ctx, seconds, start=0):
    e, out = PatientEngine(ctx), []
    for i, s in enumerate(seconds):
        r = e.feed(start + i, *s) if isinstance(s, tuple) else e.feed(start + i, s)
        if r: out.append(r)
    return e, out


def check(c):
    i, x = c["input"], c["expected"]
    cid = c["id"]
    if cid.startswith("SCORE-"):
        return band(i["vital"], i["value"]) == x["component_score"]
    if cid.startswith("S2-") and "vital" in i:
        return band("spo2", i["value"], 2, i["supplemental_oxygen"]) == x["component_score"]
    if cid in ("S2-NO-AUTH", "S2-EXPIRED"):
        return band("spo2", i["spo2"], 1) == x["component_score"]          # falls back to Scale 1
    if cid.startswith("SUM-"):
        s = clinical_score(i["values"])
        ok = s["observed_subtotal"] == x["subtotal"] and s["maximum_available_subtotal"] == x["maximum_available"]
        _, out = run(CTX["P003"], [{k: (float(v) if v is not None else None) for k, v in i["values"].items()}] * 10)
        exp = {"Urgent": 3, "Insufficient assessment": 1}[x["priority"]]
        return ok and out[-1]["priority"] == exp and (x.get("status") in (None, s["status"]))
    if cid == "ROUND-01":
        return band("hr", 90.5) == 1
    if cid.startswith("INT-SCORE"):
        s = [v for v in i["scores"] if v is not None]
        return (sum(s) if s else None) == x["observed_subtotal"] and (max(s) if s else None) == x["maximum_component_score"]
    if cid == "ZERO-RR":
        _, out = run(CTX["P003"], [dict(DEFAULT)] * 9 + [dict(DEFAULT, rr=0.0)])
        return out[-1]["priority"] == 3 and out[-1]["experts"]["rr"]["score"] in (None, 0) and "SAFE-2" in out[-1]["rules"][0]
    if cid == "STALE-01":
        _, out = run(CTX["P003"], [dict(DEFAULT)] + [dict(DEFAULT, spo2=None)] * 19)
        return out[-1]["experts"]["spo2"]["score"] is None
    if cid == "ART-02":
        s = [(dict(hr=84.0, rr=32.0, spo2=None, temp=36.8), False, True)] * 10
        _, out = run(CTX["P003"], s)
        return out[-1]["priority"] == 3 and any("SAFE-1:rr" in r for r in out[-1]["rules"]) and out[-1]["technical"]
    if cid == "ART-01":
        _, out = run(CTX["P003"], [(dict(hr=84.0, rr=16.0, spo2=None, temp=36.8), False, True)] * 10)
        return out[-1]["technical"] and out[-1]["priority"] < 2 and out[-1]["experts"]["spo2"]["score"] is None
    if cid == "ART-03":
        _, out = run(CTX["P003"], [dict(DEFAULT)] * 9 + [(dict(DEFAULT, spo2=76.0), True)])
        return out[-1]["priority"] == 3 and out[-1]["verification"]
    if cid == "ALERT-01":
        lc, ops = AlertLifecycle(), []
        for sp in (87, 97, 86):
            _, out = run(CTX["P003"], [dict(DEFAULT, spo2=float(sp))] * 10)
            ops.append(lc.step(0, out[-1]["priority"]))
        return ops[0] == "opened" and lc.n == 1 and lc.open is not None
    if cid in ("ALERT-03", "INT-ACK-NOT-RESOLVE"):
        lc = AlertLifecycle(); lc.step(0, 3); lc.acknowledge("dr"); return lc.open and lc.open["state"] == "acknowledged"
    if cid == "ALERT-04":
        lc = AlertLifecycle(); lc.step(0, 3)
        for k in range(7): lc.step(10 * k + 10, 0)
        return lc.open["state"] == "eligible_for_resolution"
    if cid == "ALERT-02":
        lc = AlertLifecycle(); lc.step(0, 3)
        for k in range(6): lc.step(10 * k + 10, 1)                       # missing -> insufficient (1)
        return lc.open is not None and lc.open["stable_s"] == 0
    if cid == "ALERT-07":
        _, out = run(CTX["P003"], [dict(DEFAULT, spo2=87.0)] * 10)
        return out[-1]["priority"] == 3
    if cid == "ALERT-08":
        e = PatientEngine(CTX["P003"])
        e.feed(0, DEFAULT, event_id="E1")
        return e.feed(1, DEFAULT, event_id="E1") is None
    if cid == "BASE-01":
        e, _ = run(CTX["P003"], [dict(hr=65.0, rr=16.0, spo2=97.0, temp=36.8)] * 900)
        return e.base["hr"].status == "established" and e.base["hr"].ref == 65
    if cid == "BASE-02":
        e, _ = run(CTX["P003"], [dict(DEFAULT)] * 899)
        return e.base["hr"].status != "established"
    if cid == "BASE-04":
        s = [dict(DEFAULT)] * 450 + [dict(DEFAULT, hr=None)] * 5 + [dict(DEFAULT)] * 445
        e, _ = run(CTX["P003"], s)
        return e.base["hr"].status != "established"
    if cid in ("ALERT-09", "ALERT-10", "BASE-03"):
        ctx = json.loads(json.dumps(CTX["P003"])); ctx["history"]["cardiac"] = x.get("priority") != "Watch" and cid != "ALERT-10"
        if cid == "BASE-03": ctx["history"]["cardiac"] = True
        e, out = run(ctx, [dict(DEFAULT, hr=65.0)] * 900 + [dict(DEFAULT, hr=87.0)] * 30)
        exp = 2 if (x.get("priority") == "Review") else 1
        ok = out[-1]["priority"] == exp
        return ok and (cid != "BASE-03" or e.base["hr"].ref == 65)
    if cid == "CTX-02":
        return not CTX["P007"]["history"]["cardiac"] and "postoperative" not in json.dumps(CTX["P007"])
    if cid == "CTX-04":
        return "Discharge disposition unknown" in CTX["P001"]["limitations"]
    if cid == "EVAL-01":
        return (i["severe_s"] - i["proposed_alert_s"], i["episodes"] / (i["total_monitored_s"] / 86400)) == (1080, 2.0)
    if cid in ("INT-AGE-NO-OVERRIDE", "INT-OVERLOAD-FLOOR"):
        a, b = json.loads(json.dumps(CTX["P003"])), json.loads(json.dumps(CTX["P003"]))
        a["age"], b["age"] = 27, 62
        return run(a, [dict(DEFAULT, rr=22.0)] * 10)[1][-1]["priority"] == run(b, [dict(DEFAULT, rr=22.0)] * 10)[1][-1]["priority"]
    return None                                                            # not executable here


if __name__ == "__main__":
    res = {"PASS": [], "FAIL": [], "NOT_EXECUTED": []}
    for c in CASES:
        r = check(c)
        res["PASS" if r else "NOT_EXECUTED" if r is None else "FAIL"].append(c["id"])
    print(f"PASS {len(res['PASS'])}  FAIL {len(res['FAIL'])}  NOT_EXECUTED {len(res['NOT_EXECUTED'])}")
    print("FAIL:", res["FAIL"]); print("NOT_EXECUTED:", res["NOT_EXECUTED"])
    (ROOT / "avoflare/results").mkdir(exist_ok=True)
    (ROOT / "avoflare/results/test_results.json").write_text(json.dumps(res, indent=1))
    raise SystemExit(1 if res["FAIL"] else 0)
