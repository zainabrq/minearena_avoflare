# Mandatory acceptance and judge demo checklist
Each check requires executed evidence, not slides, source code alone or planned tests. Record PASS/FAIL/BLOCKED, timestamp, commit and output path. The clinical 81 fixtures in 03_clinical_intelligence/08_clinical_test_cases.json remain the authoritative component test suite; this file adds integration checks only.

| ID | Requirement | Demonstration / pass condition |
|---|---|---|
| INT-01 | 3.1 | Submit actual R4 Vital Signs Observations for four vitals from simulator through agreed API. Validate with R4 Vital Signs profiles, LOINC 8867-4/2708-6/9279-1/8310-5, UCUM /min,%,/min,Cel, subject, category, status, effective time. Retrieve stored resources from HAPI FHIR and compare source values/identity. |
| INT-02 | 3.1 | Missing reading represented with appropriate dataAbsentReason, no fabricated quantity. Reject wrong subject, incompatible unit or malformed FHIR; show persistence/retry evidence and no cross-patient assignment. |
| INT-03 | 3.2 | Simulator streams individual patients at two configured sample rates; demonstrate gradual drift, genuine spike, dropout, motion noise, joint probe removal (SpO2 null/zero AND observed HR flatline), synthetic temp. Preserve offline underlying state. |
| INT-04 | 3.2 | Replay BIDMC HR/RR/SpO2 through actual FHIR API and HAPI; demonstrate real-time or accelerated playback; preserve source recording/time, no invented temp or Synthea linkage. |
| INT-05 | 3.3 | Show >=5 Synthea profiles with verified conditions and medication records, source references and selected discharge encounters. Preserve unknown disposition/current use; if explicit home discharge required, obtain additional verified profiles rather than inventing. Show context changes actual applicable rules/alerts, not only profile display. |
| INT-06 | 3.4 | Run scoring boundary fixtures, demonstrate partial NEWS2 coverage, P002-H authorized Scale2 vs standard Scale1 for same 91%, unknown oxygen status case, baseline-based gradual deviation and freeze. |
| INT-07 | 3.5 | Demonstrate isolated motion/probe artifact suppresses false clinical alarm where evidence confirms fault; true deterioration with fault still escalates from reliable evidence. Detect missing, implausible, flatline; do not discard zero RR automatically. |
| INT-08 | 3.6 | Live clinician dashboard displays vitals, history, baseline, scores and Watch/Review/Urgent, with reading, rule and patient profile fact/evidence for each alert; separate quality and monitoring status; acknowledge does not resolve. |
| INT-09 | 3.7 | Replay stable recovery, slow deterioration, artifact-only scenarios through both systems; generate actual lead time, missed events, false alerts and alerts/patient-day, with raw logs and predeclared labels. |
| INT-10 | Safety | Critical-normal-critical recurrence, cold start, missing data during urgent, solver failure, delayed HAPI and stale model response: immediate safety continues, no unjustified downgrade, no hidden labels used. |
| INT-11 | Isolation | Ten concurrent patients, distinct sessions and state; reject unauthorized subject and duplicate/replay events without double-counting. Measure latency and report failures. |

## Demo order (suggested, adapt to allotted time)
1. Show five qualifying patient profiles and evidence; select P001 and P002-H.
2. Start simulator and BIDMC; show actual network ingestion and HAPI retrieval.
3. Show stable recovery then slow deterioration, baseline divergence, score and explained alert.
4. Show Scale 1 vs authorized Scale 2; show joint probe removal and separate technical alert; show genuine deterioration during fault.
5. Show actual paired performance report and limitations, then manifest/PINN-ODE if implemented. Explain clinical decision support, not diagnosis. Use prerecorded run outputs only as supplemental evidence, not substitute for working demo.

Optional patient symptom application, FHIR Flag/CommunicationRequest escalation and Kannada/Hindi notifications do not substitute for mandatory checks. Preserve architecture V4.1; no new experts.


## V4.1 integration revision (Backend V1.1)
Additional integration checks: native FHIR authenticated endpoint and HAPI GET all four; actual BIDMC three-vital replay and isolated simulated alerts; existing internal/FHIR identity mapping; subtotal/max and clinical/processing separation; P0 bypass while model/HAPI unavailable; identical retry and no duplicate records. See 05 BE36–50 and 06 security plan.
