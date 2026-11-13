# Pre-deployment test run (2026-11-13 08:59:29)

PASS 31 · FAIL 0 · CONFIG REQUIRED 1 · full scorecard 72/72

| ID | Requirement | Result | Evidence |
|---|---|---|---|
| R01 | 10 patients x 15 days of wearable data (10 pps device, 1 Hz gateway) | PASS | 10 patients, 1296000 s each |
| R02 | Medical rules: PS03 spec fixtures (NEWS2 bands, Scale 2, baseline, artifacts, alert lifecycle) | PASS | NOT_EXECUTED: ['CTX-01', 'CTX-03', 'CTX-05', 'CTX-06', 'ART-04', 'ART-05', 'ALERT-05', 'ALERT-06', 'INT-REPLAY-ISOLATION'] |
| R03 | Continuous risk score decides by threshold (ML-1, raises to Review only) | PASS | threshold 0.9, 359.0 s vs 769.0 s |
| R04 | Accurate: all deteriorations detected before severe, fewer false alerts than NEWS2 | PASS | 9/9, min lead 341.0 s, false/pt-day 9.127 vs 142.02 |
| R05 | Evidence-based metrics with confidence intervals | PASS | AUROC 0.9613 [0.9034, 0.9917] |
| R06 | Digital twin trained and forecasting 5/15/30 min on held-out patients | PASS | ['P008', 'P009', 'P010'] |
| R07 | Twin uncertainty calibrated (RR band >= 90% coverage) | PASS | held-out calibrated coverage [0.979, 0.982, 0.977] |
| R08 | Blood pressure and HRV with scores and tests | PASS | PASS 27  FAIL 0; 9/9, 0.19 false/pt-day |
| R09 | SBP score false flags below 1 per patient-day | PASS | 4/9 events, 0.18 false/pt-day |
| R10 | Urgent alert goes first to the patient's own doctor | PASS | P003 -> DR2 (Dr. S. Menon) |
| R11 | Different patients route to different doctors (not one fixed doctor) | PASS | 4 distinct primary doctors |
| R12 | Doctor unavailable -> nurse | PASS | -> NR3 |
| R13 | Nurse unavailable -> substitute doctor | PASS | -> DR4 |
| R14 | Substitute unavailable -> management office | PASS | -> MG1 |
| R15 | No acknowledgement: escalates through the whole chain, then reminds management | PASS | ['doctor', 'nurse', 'substitute_doctor', 'management'] |
| R16 | Different information to doctor, nurse, substitute and management | PASS | 4 distinct messages, 3 distinct guidance lists |
| R17 | Phone/watch notifications carry criticality only | PASS | URGENT: Patient P003 needs attention. Open Avoflare when available. |
| R18 | Phone/smartwatch push delivery configured | CONFIG REQUIRED | NTFY_URL is not set: in-app inbox + browser notifications only; set NTFY_URL to deliver to phones/watches |
| R19 | Alarm sounds for every unacknowledged Urgent alert, for all clinical staff, until acknowledged | PASS | urgentAll() + 600 ms alarm loop |
| R20 | All supplied dashboard assets used (logo, avatars, watch stills and videos, login video) | PASS | referenced 8/8, served 8/8 |
| R21 | Clinical decision support disclaimer present | PASS | shell footer + login |
| R22 | Platform suite (FHIR, gateway security, roles, patient app, twin, BIDMC isolation, Doctor Ava, timeline, notifications) | PASS | 56/56 |
| R23 | Nurse can propose a medication (pending until a doctor decides) | PASS | 200 |
| R24 | Nurse cannot approve medication | PASS | 403 |
| R25 | Doctor decision requires a note | PASS | 400 |
| R26 | Doctor approves; second decision on the same request is refused | PASS | 200 then 409 |
| R27 | Approved medication appears in the patient's app | PASS | 2 approved items |
| R28 | Doctor shift: start shift puts the doctor on duty | PASS | since your last shift ended |
| R29 | Shift view lists only the doctor's own patients with what happened (alerts, events, symptoms, medication) | PASS | ['P001', 'P002', 'P006', 'P008', 'P009', 'P010'] |
| R30 | Doctor signs off each patient review; cannot review another doctor's patient | PASS | own 200, other 403 |
| R31 | Ending the shift takes the doctor off duty (escalations skip them) | PASS | available False |
| R32 | Acknowledge and resolve are separate; resolve needs a doctor and a reason | PASS | nurse 403, empty reason rejected |