# 05 | Patient identity, state and consistency

V4.1 section 15: state key = (source namespace, patient/subject ID, variant ID, session ID). Patient ID is the Patient KB lookup key, not authorization or a complete state key. Map FHIR Patient ID via trusted registry. Manifest identity and references inherit the full authorized runtime scope even if the illustrative PDF example omits namespace; reconcile field mapping with final shared contracts.

## State inventory
| State | Contents / lifecycle |
|---|---|
| Identity registry | producer scope, patient mapping, source, variant, session, clock and cadence; immutable within run |
| Accepted event journal | original FHIR hash, source/receipt times, dedup status, persistence receipt |
| Context cache | patient record version, clinical cutoff, knowledge version, context reference, unknowns |
| Quality/rolling history | raw references, valid/suspect/missing, gaps, coverage, adaptive window state |
| Baseline | per-vital calibration, established values, eligibility, freeze/resume and version |
| Clinical assessment | component scores, available coverage, expert evidence, concern, reliability |
| Safety/alert episodes | escalation floor, latest and highest unresolved priority, lifecycle, evidence, actions |
| Model state | manifest, checkpoint, frame, parameters, forecast/trust references and versions |
| Care/recovery | approved plan, clinician authorization, patient reports, task status |
| Publication/outbox | scoped sequence, event ID, delivery status, persistence and notification attempts |

Use PostgreSQL or SQLite for prototype according to actual concurrency and existing code; use Redis Streams or equivalent durable mechanism if needed. A single logical writer per session or transactional CAS is mandatory. Use durable transaction boundary for event acceptance, processing status and outbox where possible; document crash recovery for cross-store operations. Do not assume exactly-once transport; implement at-least-once delivery plus idempotent effects. Retain unresolved alert and safety state across restarts.

## Ordering
Source time governs physiological analysis. Keep bounded lateness policy and watermarks configurable, explicitly document chosen tolerance. Do not advance latest state backward when late event arrives; preserve historical record, flag lateness and assess serious late evidence per safety policy without presenting as fresh. Do not rewrite prior decisions silently; corrections append versioned evidence. Sequence gaps and source gaps distinct. Model jobs read immutable snapshots; commit only if state/context versions still compatible. On conflict recompute or discard, never overwrite newer safety floor.

## Baseline/context
Use 03 specs as authoritative. Historical observations are references, not established stable baseline. Context retrieval as-of selected clinical cutoff; no future data, no hidden simulator state. Invalidate cache on verified authorized patient record/knowledge update; new context version and evidence trail. Missing context never becomes normal. Calibration and freeze/resume per clinical policy; all four experts run with same snapshot. Reset/replay creates new session; no carryover unless explicitly authorized and recorded, not default. P002-H and P002 isolated; BIDMC separate.

## Alerts
Implement existing clinical policy exactly, including 30s persistence rules, 60s recovery verification engineering defaults, and separate technical episode recovery. Clinical priority Watch/Review/Urgent/Insufficient assessment; physiological concern, reliability, monitoring and forecast status independent. Acknowledge is not resolve. Unresolved Urgent stays visible even when latest readings improve; authorized clinician closure with reason and version check. New episode only after resolution and new trigger. Missing/suspect cannot count as recovery; verified artifact cannot erase reliable clinical concern. Store escalation and notification dedup separately. Immediate safety direct input independent of neural model.

## Recovery/retention
Persist enough scoped state to restart or reconstruct from event history; validate checkpoint hash and versions, replay idempotently. No hidden labels in runtime. Retention and deletion configured for synthetic demo, document policy; restrict exports. Separate online state from offline evaluation ground truth. Clear client caches on logout or scope switch. Never expose raw patient records to unauthorized operators.


## V4.1 integration revision (Backend V1.1)
PostgreSQL authoritative operational records: devices/assignments, context snapshots, observation_events, outbox_events, processing_attempts, decisions, alerts, delivery attempts, acknowledgements, model results, security/audit. Redis cache/stream state is not clinical source of truth. Per-key single writer or transactional CAS for window, baseline, manifest, score, current assessment and episode; worker lane switches must not reorder or overwrite newer state. Event ID and original body hash unique within authorized identity; each downstream side effect unique by event + purpose. Durable event/outbox committed in same transaction, dispatch may duplicate, consumer idempotent; ack only after result recorded. Persist unresolved safety floor and episode versions, restore on restart. Delivery receipt/acknowledgement never clears clinical episode. No future context or ground truth in state.
