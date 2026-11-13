# MineArena PS03 — Performance report (blank template)
Status: NOT RUN. Replace blanks only with actual evaluation outputs. Engineering synthetic/replay results, not clinical validation or diagnosis.

Evaluation ID: —  Date: —  Commit: —  Policy version: —  Comparator version: —  Hardware: —  Model status: —  Run IDs/split: —  Data hashes: —

| Metric | Fixed threshold | V4.1 | Notes / raw evidence |
|---|---|---|---|
| Monitored patient-days | — | — | source time |
| Deterioration events / detected / missed | — | — | independently labelled |
| Median lead time (s), n | — | — | detected events with endpoint |
| Mean lead time (s), n | — | — | |
| Median detection delay (s), n | — | — | |
| False clinical episodes | — | — | |
| Artifact-related false clinical episodes | — | — | |
| Clinical alerts per patient-day | — | — | |
| Technical / verification episodes per patient-day | — | — | |
| Total unique alert episodes per patient-day | — | — | |
| Artifact precision / recall / coverage | — | — | |
| FHIR validation and persistence counts | — | — | |
| Explanation completeness | — | — | |
| Safety latency p50/p95/p99 | — | — | |
| Routine latency p50/p95/p99 | — | — | |

Paired lead-time improvement (matched events detected by both): —; n: —. Separate misses: —.

## Scenario breakdown
Stable recovery: —. Slow deterioration: —. Artifact-only: —. Combined fault and deterioration: —. Intermittent: —. Cold start: —. BIDMC replay (no clinical labels): —.

## Mandatory acceptance checks
INT-01 through INT-11: pending. Link executed logs and resource retrieval evidence.

## Optional forecast report
Model, horizon, target vital, test n, MAE, RMSE, interval coverage/width, abstention, failures, latency: —.

## Limitations and failures
Synthetic trajectories, limited real replay, partial NEWS2, unvalidated prototype policies, cohort evidence gaps, test coverage and any failed integration: —. No claimed clinical validation.


## V4.1 integration revision (Backend V1.1)
### Infrastructure and resilience (fill actual results only)
| Metric | Target / context | Measured | Evidence |
|---|---|---|---|
| P0 ingress to WS handoff p95 | <500ms proposed | Pending | |
| P1 first eligible result p95 | <750ms proposed | Pending | |
| P2 first eligible result p95 | <1000ms proposed | Pending | |
| Source sample to browser receipt | full end-to-end | Pending | |
| Client receipt to clinician ack | separate human time | Pending | |
| HAPI backlog and recovery | no duplicate or lost accepted events | Pending | |
| Security rejection and side effects | isolated cases | Pending | |
| P0 under model overload | floor unchanged | Pending | |
Include p50/p95/p99, n, run ID, environment, errors and limitations for all measured timing.
