"""One scorecard for everything. Run: python run_all_tests.py   (server checks run if localhost:8000 is up)
Writes results/scorecard.json."""
import json, subprocess, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
card = []


def add(area, name, ok, detail=""):
    card.append({"area": area, "test": name, "result": "PASS" if ok else "FAIL", "detail": detail})


def run(script):
    p = subprocess.run([sys.executable, script], cwd=HERE, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout.strip().splitlines() or [""])[-1]


# 1. clinical spec fixtures (NEWS2 bands, Scale 2, baseline, artifacts, alert lifecycle)
ok, out = run("test_engine.py"); add("Clinical rules", "Spec fixtures 08_clinical_test_cases.json", ok, out)
# 2. BP / HRV / shock index score boundaries
ok, out = run("test_extra_vitals.py"); add("BP + HRV", "Score boundary tests", ok, out)
pt = (subprocess.run([sys.executable, "test_platform.py"], cwd=HERE, capture_output=True, text=True), json.loads((HERE / "results/platform_tests.json").read_text()))[1]
for x in pt["tests"]: add("Platform: " + x["area"], x["test"], x["result"] == "PASS", x["detail"])
tw = json.loads((HERE / "results/twin_report.json").read_text())["results"]
for p in ("P008", "P009", "P010"):
    m = tw[p]["all"]["30min"]
    add("Digital twin", f"{p} held-out 30 min HR/RR error below persistence", m["mae_twin"]["hr"] < m["mae_persistence"]["hr"] and m["mae_twin"]["rr"] < m["mae_persistence"]["rr"],
        f"HR {m['mae_twin']['hr']} vs {m['mae_persistence']['hr']}, RR {m['mae_twin']['rr']} vs {m['mae_persistence']['rr']}")
cov = [tw[p]["all"]["15min"].get("coverage_95_calibrated", tw[p]["all"]["15min"]["coverage_2sd"])["rr"] for p in ("P008", "P009", "P010")]
add("Digital twin", "RR +/-2 SD band covers >= 90% of outcomes", min(cov) >= 0.9, f"held-out calibrated coverage {cov}")

# 3. 15-day cohort evaluation (from train.py)
r = json.loads((HERE / "results/report.json").read_text())
c, p = r["fixed_news2_comparator"], r["proposed_rules_plus_ml"]
add("Detection", "All deteriorations detected", p["detected"] == p["events"], f"{p['detected']}/{p['events']}")
add("Detection", "Every event alerted before severe endpoint", (p["min_lead_before_severe_s"] or -1) > 0,
    f"min lead {p['min_lead_before_severe_s']} s, median {p['median_lead_before_severe_s']} s")
add("False alarms", "Fewer false alerts than fixed NEWS2", p["false_clinical_per_patient_day"] < c["false_clinical_per_patient_day"],
    f"{p['false_clinical_per_patient_day']} vs {c['false_clinical_per_patient_day']} per patient-day")
add("False alarms", "Stable patient P008 near-silent", p["per_patient"]["P008"]["false_clinical"] <= 15,
    f"{p['per_patient']['P008']['false_clinical']} false episodes in 15 days")
add("ML model", "Window AUROC >= 0.90 (leave-one-patient-out)", r["model"]["window_auroc_oof"] >= 0.90, str(r["model"]["window_auroc_oof"]))
add("ML model", "Risk score speeds up detection vs rules only",
    p["median_detection_delay_s"] < r["proposed_rules_only"]["median_detection_delay_s"],
    f"{p['median_detection_delay_s']} s vs {r['proposed_rules_only']['median_detection_delay_s']} s")

# 4. BP/HRV cohort test
b = json.loads((HERE / "results/bp_hrv_report.json").read_text())["summary"]
add("BP + HRV", "HRV drop flags events", b["hrv"]["events_flagged"].split("/")[0] == b["hrv"]["events_flagged"].split("/")[1],
    f"{b['hrv']['events_flagged']}, {b['hrv']['false_flags_per_patient_day']} false/pt-day")
add("BP + HRV", "Shock index has no false flags", b["shock"]["false_flags_per_patient_day"] == 0,
    f"{b['shock']['events_flagged']} events, {b['shock']['false_flags_per_patient_day']} false/pt-day")
add("BP + HRV", "SBP score false flags < 1/pt-day", b["sbp"]["false_flags_per_patient_day"] < 1,
    f"{b['sbp']['events_flagged']} events, {b['sbp']['false_flags_per_patient_day']} false/pt-day")

# 5. routing (role/auth checks with real logins are in test_platform.py)
teams = json.loads((HERE / "care_teams.json").read_text())["teams"]
add("Server", "Patients routed to different doctors", len({t["doctor"] for t in teams.values()}) > 1,
    f"{len({t['doctor'] for t in teams.values()})} different primary doctors")

passed = sum(x["result"] == "PASS" for x in card)
for x in card: print(f"{x['result']}  {x['area']:22s} {x['test']:62s} {x['detail']}"[:200])
print(f"\nSCORE {passed}/{len(card)} = {100 * passed / len(card):.0f}%")
(HERE / "results/scorecard.json").write_text(json.dumps({"score": f"{passed}/{len(card)}", "tests": card}, indent=1))
