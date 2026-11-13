"""Builds results/evaluation_report.html from the result files (every number comes from results/*.json)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = lambda f: json.loads((HERE / "results" / f).read_text())
rep, met, bp, card, tw = R("report.json"), R("evaluation_metrics.json"), R("bp_hrv_report.json"), R("scorecard.json"), R("twin_report.json")

# V4.1 conformance: (layer, component, status, evidence)  status: B built, P partial, N not built
ARCH = [
 ("L1 Data sources", "Virtual wearable (10 pps -> 1 Hz)", "P", "sim.py reproduces the scenario knots from the physiological config; MATLAB source not supplied"),
 ("L1 Data sources", "BIDMC real recordings", "B", "isolated replay through the same engine (server.run_isolated); RR zeros preserved, no temperature"),
 ("L1 Data sources", "Synthea clinical registry", "B", "patient_kb_v1.json loaded by engine.load_context"),
 ("L1 Data sources", "Patient recovery inputs", "B", "patient app: task completion and symptom check-in (care.py)"),
 ("L2 Secure gateway", "Device identity, authentication", "B", "HMAC-signed bundles per device, timestamp window, nonce replay protection (records.verify)"),
 ("L2 Secure gateway", "FHIR validation", "B", "R4 Observation, LOINC 8867-4/9279-1/2708-6/8310-5, UCUM units, OperationOutcome on error"),
 ("L2 Secure gateway", "Integrity & replay protection", "B", "idempotent receipts, 409 on conflicting payload, nonce reuse rejected"),
 ("L2 Secure gateway", "Signal quality, missingness, artifacts", "B", "engine._quality: missing/invalid/suspect/artifact, spikes, flatline, probe-off"),
 ("L2 Secure gateway", "Adaptive 5/10/15 s windows", "P", "fixed 10 s clinical windows, 15 s twin frames; safety on every sample"),
 ("L2 Secure gateway", "Patient-aware load balancing", "N", "single process; P0-P3 lanes not separated"),
 ("Hot path", "FastAPI real-time path, safety, notification", "B", "server.py + engine SAFE rules, WebSocket"),
 ("Cold path", "Clinical record store (HAPI FHIR R4)", "P", "durable SQLite FHIR store + outbox + circuit breaker; forwards to a real HAPI server only when HAPI_URL is set"),
 ("L3 Context", "Patient KB", "B", "conditions, medication history, demographics"),
 ("L3 Context", "Shared clinical KB", "P", "rules implemented in code; 02_shared_clinical_kb.json not loaded at runtime"),
 ("L3 Context", "Expert 1 Patient context", "B", "history flags, limitations, no inferred surgery"),
 ("L4 Experts", "Experts 2-5 HR, RR, SpO2, Temp", "B", "score, baseline delta/z, Theil-Sen slope, persistence, concern"),
 ("L4 Experts", "Partial NEWS2 + personal baseline", "B", "Scale 1/2, median/MAD baseline, freeze on concern"),
 ("L5 Manifest", "Textual physiological state manifest", "B", "twin.manifest every 15 s: versioned, parent chain, semantic hash, no history or labels"),
 ("L6 Digital twin", "264-slot context-adaptive encoder", "P", "registry ordering and masks; about 108 of 264 slots filled, rest masked; twin consumes a compact subset"),
 ("L6 Digital twin", "Hybrid PINN-ODE core + forecasts", "P", "PyTorch RK4: baseline relaxation + spec HR coupling + neural residual, 4-member ensemble, 5/15/30 min; equations provisional pending approval"),
 ("L7 Trustworthy", "Uncertainty engine", "P", "ensemble spread + measurement quality; bands under-cover RR and SpO2 (not yet calibrated)"),
 ("L7 Trustworthy", "Counterfactual engine", "B", "isolated branches A original, B exclude suspect, C measurement +/-, D tau x0.8/x1.2"),
 ("L7 Trustworthy", "Trust / evidence / consistency / validity gate", "B", "OOD distance, bounds, non-finite and missing-input abstention; rule IDs and values as evidence"),
 ("L8 Decision", "Evidence-constrained decision (Watch/Review/Urgent)", "B", "engine.decide CLIN-1..6 + ML-1; forecasts cannot change priority"),
 ("L8 Decision", "Independent clinical safety supervisor", "B", "SAFE-1/2/3 on every sample, no model dependency"),
 ("L9 Action", "Expert 6 Medication & intervention", "B", "review items from history + evidence, clinician approve/dismiss, audited; no doses"),
 ("L9 Action", "Expert 7 Patient recovery", "B", "daily activity, overnight HR trend, plan progress, symptoms; no recovery percentage"),
 ("L10 Human", "Clinician command center", "B", "web/app.html to 07_dashboard spec, using the supplied logo, avatars, watch and login videos"),
 ("L10 Human", "Patient recovery assistant", "B", "web/patient.html: plan, tasks, symptoms, medicines, care team"),
 ("L10 Human", "Hospital record interface", "B", "GET /fhir/Observation searchset, history tab"),
 ("L10 Human", "Evaluation & security console", "B", "replay, comparative results, FHIR inspection, latency, predefined attack tests, audit"),
 ("Governance", "Human accounts, roles, audit", "B", "PBKDF2 passwords, HttpOnly session, role checks, patient isolation, audit table"),
]
pts = {"B": 1, "P": 0.5, "N": 0}
conf = round(100 * sum(pts[a[2]] for a in ARCH) / len(ARCH))
data = {"twin": tw, "rep": rep, "met": met, "bp": bp, "card": card, "arch": ARCH, "conf": conf,
        "scen": {l["patient_id"]: l["scenario"].replace("_", " ") for l in json.loads((HERE / "data/labels.json").read_text())},
        "counts": {s: sum(a[2] == s for a in ARCH) for s in "BPN"}}

TEMPLATE = (HERE / "report_template.html").read_text(encoding="utf-8")
(HERE / "results/evaluation_report.html").write_text(TEMPLATE.replace("/*DATA*/", json.dumps(data)), encoding="utf-8")
print("conformance", conf, data["counts"])
