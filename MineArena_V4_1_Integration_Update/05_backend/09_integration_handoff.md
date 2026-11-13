# 09 | Teammate handoff and unresolved dependencies

The authoritative 40-page V4.1 PDF fixes architecture, not every implementation detail. Page 37 notes earlier contracts require revision; page 40 explicitly leaves equations, bounds, contracts, clinical policies and model validation as implementation dependencies. Do not treat illustrative IDs or example values as actual patient records.

| Input | Owner | Evidence required | Blocking scope |
|---|---|---|---|
| Existing FastAPI/FHIR source | FHIR teammate | source tree, actual route, dependencies, run command, tests | actual integration |
| HAPI setup | FHIR teammate | R4 version, capability statement, private URL config, validation and actual create/read evidence | PS 3.1 |
| Patient mapping | FHIR + clinical team | internal/FHIR IDs, source refs, variant and replay mappings | authorized ingestion |
| Producer interface | MATLAB + FHIR teammates | actual adapter, sample FHIR, cadence, source clock, IDs, missingness and replay evidence | PS 3.2 |
| Current shared contracts | Architecture teammate | Pydantic/JSON Schema versions, compatibility and example fixtures | wire integration |
| Clinical rules | Clinical team | existing 03 specs and test outcomes, review engineering thresholds | PS 3.3–3.6 |
| Model interface | AI teammate | exact manifest/encoder/model/trust contracts, artifact status and runtime deadline | advanced P1/P2 only |
| Mathematical model | MATLAB + AI team | equations, coefficients, units, bounds, validation and training data | model forecasting |
| Evaluation inputs | MATLAB + integration | labelled offline trajectories, run metadata and actual comparator outputs | PS 3.7 |

## Contract inventory from V4.1
ObservationEventV1, ObservationWindowV1, PatientKBRecordV1, ClinicalContextV1, KnowledgeRuleV1, BaselineStateV1, ClinicalScoreV1, ExpertInputV1, ExpertEvidenceV1, PhysiologicalManifestV1, EncoderFrameV1, ODEParameterStateV1, PatientTwinStateV1, NeuralForecastV1, TrustAssessmentV1, SafetyAssessmentV1, ClinicalDecisionV1, ClinicalReportV1, CarePlanV1. Additional transport envelopes/episode/action records must be mapped explicitly to actual code, not presented as already frozen shared contracts.

## Handoff checklist
- Obtain current repository and inspect implemented/tested vs planned. Do not replace working FHIR implementation.
- Agree actual auth protocol, event identity, timestamps, API response, queue durability, idempotency and patient scope.
- Record contract mapping and open decisions; preserve existing UI and clinical specs.
- Demonstrate one simulator observation and one BIDMC observation through actual API/HAPI before multi-stream integration.
- Run mandatory P0 before research model; maintain explicit unavailable states.
- Final integration owner confirms no new architecture layers and produces evidence-backed status.

## Decisions proposed in this package
Durable outbox, scoped publication cursor, conditional FHIR create/deterministic ID, HMAC fallback, per-key transactional state, bounded queues and explicit API mapping are engineering implementation options within V4.1; select compatible choices with existing code. No actual implementation status or test pass inferred from these specifications. Clinical thresholds and timing remain the prototype policies in 03, not validated medical rules. Source and wire details remain blocked until actual teammate handoff.


## V4.1 integration revision (Backend V1.1)
Latest FHIR handoff explicitly reports architecture/request/response/security defined, but API implementation, HAPI config, mapping, resource storage and integration not verified. No need to wait for a working service before implementation; Claude inspects repository, implements missing pieces using approved proposal, and coordinates actual interfaces. Source mapping in 02 verified against local KB + clinical registry; HAPI and device provisioning still pending. MATLAB provides observed values/quality/source time/session/cadence, separate offline ground truth and parameters. Shared Python adapter owns FHIR/signing. AI teammate's new training handoff incorporated in 06; exact equations and feature semantics pending approval. Integration owner verifies real tests and no new layers. Original V4.1 PDF plus addendum authoritative; teammate PDF retained supporting reference. Age escalation and custom-only ingestion rejected.
