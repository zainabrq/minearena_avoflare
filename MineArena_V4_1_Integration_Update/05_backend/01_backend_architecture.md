# 01 | Backend architecture and orchestration

Source: V4.1 PDF sections 1, 3–5, 10–11, 15, 17–20. This document specifies implementation within the frozen architecture.

## Responsibilities
| Component | Responsibilities | Dependency |
|---|---|---|
| Secure combined gateway | Authenticated source identity, R4 validation, integrity, deduplication, quality, routing, adaptive windows | 02, 06 |
| FastAPI hot path | Immediate safety, observed clinical pipeline, authorized APIs and notifications | 03_clinical_intelligence |
| Cold path | Original accepted observations, HAPI persistence, history and clinical reports | 03 |
| Patient context | Indexed Patient KB and shared rule retrieval, versioned context | Existing registry, clinical specs |
| Four experts and scoring | Deterministic component scores, rolling baselines, parallel findings | Clinical specs, not new agents |
| AI integration | Manifest, fixed source-time frames, twin and trust outputs | 06_ai_digital_twin |
| Decision | Safety floor, current evidence, eligible forecasts, clinical report | Clinical decision policy |
| Human care | Authorized acknowledgement, resolution, approved care, recovery inputs | Dashboard and clinical policy |
| Evaluation | Isolated replay and comparator, performance, FHIR and audit inspection | 08_evaluation |

## Execution sequence
1. Authenticate producer and authorize subject/session; validate envelope integrity and event freshness, then FHIR structure and mapping. Reject invalid identity before any patient state mutation.
2. Normalize accepted observation into ObservationEventV1, retaining original FHIR payload, ID, hash, source time and arrival time. Use a durable idempotent acceptance boundary with pending processing records. Do not claim accepted durability until confirmed. If durable store unavailable, surface failure and degraded service; prioritize immediate safety for authenticated/validated observations if possible, with explicit best-effort notification and no false persistence claim.
3. Perform lightweight quality checks and event-driven SafetyAssessmentV1; evaluate potentially critical suspect values instead of silently dropping them. Do not await HAPI, context refresh, window close, forecast or report. Use last verified authorized context when available; default Scale1 with context limitation if unavailable according to clinical policy.
4. Publish urgent safety action immediately via existing authorized channel; maintain an escalation floor in patient/session state. Separate alert episode lifecycle from current assessment.
5. Dispatch accepted event independently to cold persistence and routine gateway window processing. Use bounded queues, backpressure and visible failure counters; never silently lose observations.
6. Patient Context Expert resolves authenticated Patient KB record and applicable shared knowledge. Run four expert functions with the same context snapshot; calculate score and baseline from reliable evidence. Freeze baseline at first eligible concern; compare against previous baseline before updating.
7. Close routine windows according to 02; publish observed clinical assessment even if AI is unavailable. Build manifest and fixed 15-second causal frames with 06. Invoke model/trust processing with deadline, immutable inputs and patient/session version.
8. Merge eligible verified model outputs with observed evidence through existing decision policy. Discard stale or mismatched responses. Experimental forecasts cannot independently change priority. No model can lower a mandatory floor.
9. Persist decisions, reports, context refs, evidence links and lifecycle transitions; publish authorized snapshots and stream updates. Recovery and medication experts use verified clinical decisions and approved care only.

## Isolation and scheduling
Partition routine state by namespace + patient/subject + variant + session; single logical writer or transactional compare-and-swap per key. Parallelize independent patients, not mutations of one patient. Prioritize authenticated safety over routine, model and report tasks; reserve queue/worker capacity. Model and HAPI timeout/circuit handling must not block the safety path. No global in-memory patient singleton. Durable restart recovery must retain unresolved urgent episodes and deduplication state.

## Failure behavior
| Failure | Required response |
|---|---|
| HAPI unavailable | Continue accepted hot-path processing; queue persistence and show pending/failed storage |
| Context missing | Explicit unknown; independent safety remains; no invented personalization |
| Model unavailable/timeout | Observed decision continues, forecast failed/unavailable; no fake predictions |
| Suspect critical reading | Safety verification per clinical policy, not automatic discard |
| Queue overload | Backpressure, protected safety lane, visible degraded status and loss accounting |
| Browser disconnect | Backend continues, authorized replay/snapshot on reconnect |
| State version conflict | Retry or discard stale computation; do not overwrite newer safety floor |

## Ownership boundary
Folder 05 orchestrates; clinical algorithms are implemented once from folder 03 and imported by backend. Folder 06 owns model internals and trust computations; backend validates their contracts and eligibility. Folder 07 consumes outputs, never recomputes clinical decisions. Folder 08 receives offline labels separately. No direct browser-to-HAPI or browser-to-Patient-KB access.


## V4.1 integration revision (Backend V1.1)
Deploy NGINX at ingress; FastAPI gateway authenticates and validates native FHIR. PostgreSQL event + outbox transaction creates durable processing and persistence intent; dispatch through Redis Streams P0–P3 and separate FHIR persistence work. Independent safety computation starts immediately after validation, not after enqueue/window. P0 reserved worker delivers urgent alerts; P1 contextual review and P2 routine share the same ordered clinical timeline, never exclusive ownership of patients. Every accepted observation contributes to clinical state and persistence; urgent observations also schedule asynchronous model updates. P3 offline work only. Interactive replay has equivalent safety/clinical lanes scoped to replay recipients. Infrastructure Clinical Traffic Integrity Controller (10) lives within Layer 2/backend orchestration; separate clinical and system urgency. No dependency on HAPI/model for immediate notification. No age-based clinical escalation.
