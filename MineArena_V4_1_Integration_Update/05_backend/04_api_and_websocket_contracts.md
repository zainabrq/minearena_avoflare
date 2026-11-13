# 04 | API and WebSocket integration

These are semantic operations, not invented deployed routes. Inspect existing FastAPI OpenAPI and teammate code; create `api_mapping.md` with real method/path, authentication, request and response schemas, version, owning module and test status. Use shared Pydantic contracts from 01_architecture as authoritative wire definitions. Export OpenAPI and generate frontend types where practical. Do not create parallel APIs when an existing operation can be extended compatibly.

| Logical operation | Required data/contract | Authorization |
|---|---|---|
| Authenticate/session/logout | Existing auth session/role | user |
| Register/start producer session | namespace, patient/subject, variant, source clock, expected cadence | authorized producer/operator |
| Submit vital observation | FHIR R4 Observation + authenticated event metadata; acceptance receipt | producer scoped to session |
| List monitoring summaries | patient/session, latest values, quality, ClinicalScoreV1, ClinicalDecisionV1, episodes | assigned clinician |
| Read profile/context | authorized PatientKBRecordV1 facts, ClinicalContextV1 | assigned clinician/patient as allowed |
| Snapshot/history | ObservationEventV1, ObservationWindowV1, BaselineStateV1, timestamps, pagination | authorized scope |
| Read experts | ExpertEvidenceV1, rule/context/observation refs | clinician |
| Read twin | PhysiologicalManifestV1, EncoderFrameV1 metadata, PatientTwinStateV1, ODEParameterStateV1, NeuralForecastV1 | clinician/evaluator |
| Read trust/branch | TrustAssessmentV1 and isolated branch result | clinician/evaluator |
| List/acknowledge/resolve alert | episode, expected version, action reason, audited response | assigned clinician |
| Read reports | ClinicalReportV1, evidence refs, limitations | clinician |
| Read approved care plan | CarePlanV1, approved instructions | patient or clinician |
| Submit symptom/task/adherence | scoped report, idempotency, recorded time, actual response | patient/authorized clinician |
| Approve/modify/reject care | authorized clinician decision and version | clinician |
| Replay start/pause/reset | run/session identity, scenario/recording, speed, source-time status | evaluator/operator |
| Read performance results | actual run artifacts and metrics from 08_evaluation | evaluator |
| Inspect HAPI resources | validation, persistence and actual scoped resource | authorized clinician/evaluator |
| Read system health/audit | queue, latency, sanitized security events | operator/admin |

## Response semantics
Separate accepted, pending persistence, persisted, rejected and failed. Use consistent error envelope (FHIR OperationOutcome for FHIR-facing errors when appropriate), correlation ID, safe message, retryability and no stack traces. Use appropriate 400/422 validation, 401 unauthenticated, 403 unauthorized, 404 absent (or conceal unauthorized resource existence), 409 conflict, 429 rate limit, 503 unavailable. Map existing API behavior and document deviations. Use pagination and bounded ranges; UTC timestamps with explicit source-time mapping. Idempotent mutations require operation keys, expected state version and server-side authorization. Do not report success until action committed.

## WebSocket contract
Authenticated stream to authorized patient/session scopes. Do not put credentials in URL query parameters. Use existing approved auth mechanism; validate browser Origin and enforce subscription authorization on each request, revocation and reconnect. Logical message fields: event type, unique event ID, scoped stream sequence/checkpoint, identity, source time, publication time, schema version, state/context version, payload and correlation ID. Map to real contract; no sensitive unrelated data broadcast. Events include accepted/quality-adjusted observations, window/score/baseline, safety notifications, decision, alert lifecycle, twin/trust status, monitoring status and persistence status. Immediate safety messages bypass routine coalescing. Use a monotonic publication sequence within stream, not source timestamp, for reconnect ordering.

Snapshot plus cursor handshake: acquire consistent snapshot and sequence checkpoint; subscribe/resume after checkpoint; buffer or replay intervening events; deduplicate by ID, reject stale state updates. If retention gap, send explicit resync-required and fetch fresh snapshot. Heartbeat, timeout, bounded reconnect backoff and jitter. Bounded per-client buffers; slow client disconnect/resync rather than block ingestion or silently lose alert state. Revoked access closes affected stream. On patient switch clear old UI buffers. Backend remains source of truth; no frontend clinical scoring.

## Model interface
06 consumes immutable scoped manifest/context/feature frame; returns versioned model state, forecast status, uncertainty and trust. Reject mismatched identity, manifest/context/model version or stale source time. Timeout/failure publishes explicit unavailable/failed status and leaves observed clinical decision intact. Forecasts experimental until validated. No mock output on live stream. Counterfactual jobs have isolated branch IDs and cannot mutate patient state.


## V4.1 integration revision (Backend V1.1)
Proposed POST /api/v1/observations accepts native FHIR body plus scoped signed headers (11); 202 receipt {event_id,request_id,status:accepted,processing:queued}, no clinical priority or score. Identical authorized retry returns stored receipt; 409 for conflicting payload. OperationOutcome for FHIR validation where practical; authentication errors redacted. Add authorized operations for delivery receipt (client instance + alert/delivery IDs), clinical acknowledgement (human actor and expected episode version), clinical resolution (reason + version), queue/worker telemetry and controlled security test results. Separate handoff, client receipt, acknowledgement, resolution; WebSocket reconnect snapshot restores unresolved alerts. Report processing lane only in engineering scope. Human auth separate from producer token, no secrets in browser. Confirm actual route names in OpenAPI and mapping table.
