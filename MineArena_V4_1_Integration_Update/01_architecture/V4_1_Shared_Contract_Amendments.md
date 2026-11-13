# V4.1 shared contract amendments (logical, pending Pydantic alignment)
Do not install or revive obsolete V1 contract ZIP. Retain all 19 V4.1 contract names from the authoritative PDF. This is a field-level integration proposal, not generated authoritative Pydantic code. Architecture owner must reconcile exact field names/types with final shared models and export schema fixtures. Use additive compatible changes where possible; version breaking changes explicitly.

| Contract | Required fields / invariants |
|---|---|
| ObservationEventV1 | Full runtime key; producer/device ID, stable event ID, per-session sequence, original FHIR resource/ref/hash, source offset/effective time, signed transmission and server receipt UTC, value/unit or absence reason, quality, provenance, schema version. Per-vital observation identity even if source packet contains four. |
| ObservationWindowV1 | Key, window start/end source seconds, actual duration 5/10/15, ordered event refs, coverage per vital, quality/missingness, context and state versions, completion/watermark. |
| PatientKBRecordV1 / ClinicalContextV1 | Original patient/FHIR mapping, source/variant, version/as-of cutoff, documented facts and references, medication history vs confirmed use, authorized oxygen scale/target/status, unknowns; no future facts. |
| ClinicalScoreV1 | Component scores and eligibility, observed subtotal (nullable), maximum eligible component (nullable), scored_count, maximum_available_subtotal, theoretical_maximum=12, full NEWS2=null, context/rule refs. |
| SafetyAssessmentV1 | Event/key, mandatory floor, clinical vs verification/technical finding, raw evidence and quality, context limitation, rule version and UTC/source time. No model dependence. |
| ClinicalDecisionV1 | Clinical priority, concern, reliability, monitoring, forecast validity, action, evidence/rule/context refs, policy/state versions; processing priority and routing reason as independent metadata. |
| ClinicalReportV1 | Immutable decision/evidence refs, source time, context/rule/model versions, limitations, delivery references if relevant. |
| PhysiologicalManifestV1 | Full opaque identity, context ref, observed/baseline state, relationships, config/parameter refs, quality/uncertainty, checkpoint/parent/version/time; no clinical biography or labels. |
| EncoderFrameV1 | Key, manifest/context refs, fixed 15s source time, 264 ordered finite values, registry/normalizer versions, masks and eligibility. |
| ODEParameterStateV1 / PatientTwinStateV1 / NeuralForecastV1 / TrustAssessmentV1 | Same identity and manifest/frame versions, equation/model versions, parameters/units/bounds, observed vs estimated vs forecast, horizons, uncertainty/calibration, validity/abstention, timing and evidence. |
| KnowledgeRuleV1 / BaselineStateV1 / ExpertInputV1 / ExpertEvidenceV1 / CarePlanV1 | Existing clinical definitions unchanged; carry explicit context/rule/version/identity and provenance where relevant. |

Supporting operational interfaces (not new layers):
- IngestionReceipt: event_id, request_id, accepted_at, status, processing; no device-facing clinical score/priority by default. 202 only after reliable handoff. Identical authorized retry returns existing receipt, different body conflicts.
- RoutingRecord: identity, event ID, clinical assessment ref, processing lane P0/P1/P2/P3, reason, policy version, enqueue/worker timestamps, trace ID; lane is not severity.
- AlertDelivery: episode ID, delivery attempt ID, channel, attempted/handoff/client-received timestamps, failure/retry status; acknowledgement actor/time separate; clinical resolution actor/reason/version separate. Browser receipt is not clinician acknowledgment.
- SecurityEvent: redacted actor/source, validation gate, outcome/reason, event/request ID, timestamp, audit refs. Never secrets.
- SourceSession: authorized identity, device, cadence, replay clock and speed, mode, presentation channel. Simulation labels offline only.

Implementation gate: align enum spelling, nullability, units, timestamps, event uniqueness, FHIR identifier strategy and JSON examples across producers, backend, model and frontend. Generate actual OpenAPI and test serialization; never claim illustrative paths are deployed.
