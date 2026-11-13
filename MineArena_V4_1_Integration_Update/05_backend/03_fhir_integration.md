# 03 | FHIR R4 integration and persistence

Authoritative standard: https://hl7.org/fhir/R4/observation-vitalsigns.html (R4 4.0.1). Original PS03 section 3.1 requires actual HAPI FHIR storage, correct coding and demonstration.

## Mapping
| Vital | LOINC | UCUM code | Internal canonical unit |
|---|---|---|---|
| HR | 8867-4 | /min | bpm |
| RR | 9279-1 | /min | breaths/min |
| SpO2 | 2708-6 | % | % |
| Temperature | 8310-5 | Cel | degrees Celsius |
LOINC system `http://loinc.org`; UCUM system `http://unitsofmeasure.org`. For pulse oximetry, 59408-5 may be added as additional coding alongside the required 2708-6, per R4 core. Validate actual profile; do not conflate US Core requirements with R4 core. Support only approved units or explicitly normalize compatible conversions; store original quantity. Never change physiological value merely to meet plausible range.

## Example resource (illustrative only)
```json
{
  "resourceType": "Observation",
  "meta": {"profile": ["http://hl7.org/fhir/StructureDefinition/vitalsigns"]},
  "identifier": [{"system": "urn:avoflare:observation-event", "value": "demo-session-001-hr-0001"}],
  "status": "final",
  "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
  "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
  "subject": {"reference": "Patient/example"},
  "effectiveDateTime": "2026-11-12T10:00:00Z",
  "valueQuantity": {"value": 82, "unit": "beats/minute", "system": "http://unitsofmeasure.org", "code": "/min"}
}
```
Replace example patient, timestamp and ID with authorized real demo mapping. Example not validated against a running server. For missing observation omit valueQuantity entirely, include `dataAbsentReason` coding from `http://terminology.hl7.org/CodeSystem/data-absent-reason` with appropriate reason (e.g., `unknown` or `error` as evidence warrants); do not use null quantity, NaN, zero placeholder or both quantity and absence reason. Preserve observed zero in valid JSON and classify downstream. Validate declared profiles including any required specific profiles using R4 validator; server accepting a resource is not proof of profile conformance.

## Identity and clinical import
Load original Synthea Patient resources and referenced authorized encounters/conditions/medications/procedures needed for verified Patient KB; preserve reference mapping if server IDs change. Import idempotently, resolve references, retain source IDs and import receipts. Never replace patient history with simulator states. P002-H uses isolated synthetic variant identity and explicit hypothetical authorization; ensure its persisted demo data cannot mix with original P002. BIDMC uses independent pseudonymous replay Patient identity/namespace, not linked to Synthea. Persist synthetic provenance and replay time derivation in supported metadata or separately linked operational records. Avoid invented discharge facts. No hidden ground truth in HAPI runtime observations.

## Cold-path persistence
Durable pending record keyed by event ID and identity, original resource hash, attempt count, next retry, status, server resource ID/version, response and validation summary. Use actual HAPI capability statement and existing supported idempotency strategy: conditional create on stable identifier or agreed deterministic resource ID, with conflict detection; test concurrent retries and ambiguous timeouts. No blind POST retry that duplicates observations. Queue independent of hot path; bounded exponential backoff with jitter, permanent validation failure quarantined for review, retryable failures retained. After timeout reconcile by identifier before retry. Verify persisted resource by read and compare identity, code, effective time, quantity/absence reason and identifier. Record server-managed metadata differences separately. Do not label pending as stored. Restricted HAPI credentials server-side only.

## Reports/history
Expose authorized paginated history by mapped subject and relevant identity/session provenance, distinguish source observations from derived scores/estimates. Use approved report FHIR mapping only when contract agreed; retain structured ClinicalReportV1 with observation references regardless. Optional FHIR Flag or CommunicationRequest only if supported and authorized; never claim messages delivered without confirmation. Clinical record writes audited; do not overwrite original observations to reflect quality or prediction. Log validation failures using sanitized OperationOutcome details.

## Required evidence
Capture actual four observation submissions and returned HAPI IDs, validator result, GET resource evidence, missing-reading example, wrong-subject rejection, duplicate/retry evidence, BIDMC three-vital replay and reconciliation after HAPI outage. See 07 and 08_evaluation.


## V4.1 integration revision (Backend V1.1)
Adopt transaction Bundles when grouping related observations; each entry still individual R4 Observation with stable identifier and conditional create, verified against actual HAPI capability. Single Observation accepted immediately and persisted without waiting for missing siblings. Add Device resource per authorized source (FHIR Device is not authentication registry), Provenance for transformation/origin and selected AuditEvent for security/access where supported. Use actual original Synthea IDs from 02 mapping, verify HAPI refs after import. SpO2 2708-6 mandatory; 59408-5 may additionally be coded for pulse oximetry. HAPI R4 URL, DB and version not yet confirmed. Use HTTPX timeouts and CLOSED/OPEN/HALF_OPEN circuit breaker; retain durable pending work, retry with jitter, verify by GET and identifier, report backlog age and failures separately. No direct JPA database writes. Actual create/read/validation of four vitals mandatory; BIDMC only three measured vitals. No labels/true states in clinical records.
