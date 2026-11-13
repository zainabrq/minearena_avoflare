# 07 | Backend acceptance tests

Execute against actual backend, HAPI and source adapters. Use existing 81 clinical fixtures, dashboard tests and evaluation protocol rather than duplicating their algorithms. Record PASS/FAIL/BLOCKED, commit, configuration, run ID, timestamp, raw evidence path and reason. A planned test is not a pass.

| ID | Test and pass condition |
|---|---|
| BE01 | Import authorized Synthea records; verify >=5 qualifying profiles with conditions and medication references, selected encounters and explicit unknowns. |
| BE02 | Submit four R4 observations through actual API; validate profiles and retrieve matching HAPI resources. |
| BE03 | Missing value with dataAbsentReason persists; no fabricated quantity; zero preserved as raw evidence. |
| BE04 | Reject malformed FHIR, unsupported code/unit and wrong subject without patient-state mutation. |
| BE05 | MATLAB streams at two configured rates; individual events and source times retained. |
| BE06 | BIDMC replay three vitals, original recording offset, no temperature or Synthea linkage; actual HAPI retrieval. |
| BE07 | Same event ID/hash retried: one accepted logical event, no duplicate score/episode/resource. |
| BE08 | Same ID/different hash: conflict and audit; no overwrite. |
| BE09 | Forged signature, stale transmission, reused nonce, unauthorized subject rejected. |
| BE10 | Historical replay source timestamp accepted with fresh authorized transport metadata. |
| BE11 | 5/10/15s windows switch correctly; no lost samples, original evidence retained, gaps explicit. |
| BE12 | Immediate safety triggered before window close; notify without waiting for model/HAPI. |
| BE13 | HAPI outage: hot path continues, persistence pending, retry/reconcile one resource after recovery. |
| BE14 | Ambiguous HAPI timeout: reconcile before retry, no duplicate creation. |
| BE15 | Context retrieval failure: explicit unknown and independent safety remains. |
| BE16 | Scale1 vs authorized P002-H Scale2 same reading: component difference, isolated state. |
| BE17 | Baseline calibration, freeze and resume match clinical fixtures; missing not recovery. |
| BE18 | Probe removal pattern and motion: technical evidence; genuine reliable critical signal still escalates. |
| BE19 | Critical-normal-critical recurrence: urgent remains unresolved, acknowledge not resolve. |
| BE20 | Authorized clinician resolution audited with expected version and reason; unauthorized action rejected. |
| BE21 | Out-of-order event and stale model result cannot overwrite newer assessment/floor. |
| BE22 | Model timeout/abstention: observed decision available, explicit forecast status. |
| BE23 | Experimental forecast cannot independently change priority; eligible model never lowers safety floor. |
| BE24 | Ten concurrent patient/session streams: no cross-key context, baseline, alerts or media state. |
| BE25 | Restart/replay accepted journal: idempotent effects and unresolved urgent retained. |
| BE26 | WebSocket snapshot + sequence reconnect: no gap/duplicate effects, explicit resync on retention gap. |
| BE27 | Unauthorized patient REST/WS access denied; revoked session loses access. |
| BE28 | Slow browser client does not block safety; reconnect restores authoritative snapshot. |
| BE29 | Clinical alert contains reading, time, units, observation ref, applied rule/version, patient fact/ref or explicit unknown, limitations. |
| BE30 | Patient symptom/task reporting scoped and idempotent; no autonomous medication/plan change. |
| BE31 | Evaluation controls use independent sessions; ground truth never enters monitoring services. |
| BE32 | Actual paired stable/deterioration/artifact performance report with measured lead time and alerts/patient-day. |
| BE33 | Bounded overload test: explicit backpressure, loss accounting, protected safety and degraded status. |
| BE34 | Audit and manifest integrity tamper detection, no secrets/unauthorized clinical payloads in logs. |
| BE35 | Full frontend integration: actual live vitals, scores, alerts, HAPI and replay; unavailable model state honest. |

## Performance evidence
Measure source sampling/collection, receipt, safety assessment/publication, window closure, routine decision, frame/model completion, dashboard visible update and HAPI persistence separately. Provisional targets from clinical/UI specs: safety <2s from sampled event where streaming supports it, routine <1s after window close, model <2s after frame if available, dashboard publication-to-visible <1s. Report p50/p95/p99, throughput, queue age, errors, resource usage, run duration and ten-stream load. Use synchronized clocks or clearly identify same-process timing; source replay time is not wall latency. Batch collection delay must be disclosed. No performance claims without results.

## Release gate
Mandatory PS03 INT-01 through INT-11 in 08_evaluation are the integration gate. Failures in identity, safety, FHIR validation/persistence or mandatory demonstration block claims of completion. Advanced AI may be unavailable explicitly without blocking mandatory observed scoring; do not call full V4.1 implemented if model/trust components absent. Clinical decision support only, no clinical validation claim.


## V4.1 integration revision (Backend V1.1)
Additional V1.1 tests (all pending execution):

| ID | Pass condition |
|---|---|
| BE36 | Native FHIR endpoint accepts valid authenticated Observation; custom adapter converges to same pipeline; no bypass. |
| BE37 | SpO2 contains 2708-6; optional 59408-5 does not replace it; HAPI GET verifies both when supplied. |
| BE38 | Identical retry with fresh nonce returns prior receipt; same ID changed bytes conflicts; replay nonce rejected. |
| BE39 | Expired JWT, invalid HMAC, unauthorized session/variant and forged priority fail before clinical routing. |
| BE40 | PostgreSQL event/outbox atomic acceptance; Redis outage retains recoverable work or returns 503, never false accepted. |
| BE41 | Worker crash after commit before XACK: reclaim pending and no duplicate alert or FHIR resource. |
| BE42 | P2/P3 CPU/backlog load: protected P0 latency measured; urgent clinical floor unchanged. |
| BE43 | P0 event updates ordered clinical timeline, manifest asynchronously and persistence; no state loss. |
| BE44 | BIDMC interactive replay produces isolated alert and HAPI evidence, no live recipient; offline batch P3. |
| BE45 | Patient age variation alone does not alter clinical priority; subtotal 7/max 2 both retained. |
| BE46 | FHIR Bundle transaction failure and retry reconcile individual identifiers without duplicates. |
| BE47 | Distinct alert handoff, browser receipt, clinician ack and resolution; reconnect and authorization tested. |
| BE48 | Controller reports queue age/worker health/FHIR backlog; no global healthy claim when degraded. |
| BE49 | Signed transport timestamp current with historical source time; record23 -1 offset retained. |
| BE50 | No ground truth or scenario labels in runtime API, clinical feature stream or live model. |

Measure P0 ingress-to-WS handoff p95 <500ms as proposed target; P1/P2 first eligible result targets <750/1000ms after work ready, not full window/model. Report observed p50/p95/p99, sample count, clock validity, resource limits, queue delays, end-to-end browser receipt and human ack separately. No results yet.
