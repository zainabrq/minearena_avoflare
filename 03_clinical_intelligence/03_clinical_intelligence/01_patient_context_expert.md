# Patient Context Expert — Implementation Specification V1.0

**Project:** MineArena PS03 | **Architecture:** V4.1 (frozen)  
**Status:** Engineering specification; implementation and clinical validation pending.  
**Audience:** Claude, clinical intelligence and backend teams.

## 1. Purpose and boundaries
Implement Expert 1 as a deterministic, evidence-grounded context controller. Given an authenticated patient/session identity, retrieve the Patient KB record, determine documented clinical context, select applicable Shared Clinical KB rules, and publish one immutable, versioned ClinicalContextV1 snapshot. This is clinical decision support, not diagnosis. Do not invent clinical facts, prescribe treatment, or calculate final alert priority in this expert. Do not change V4.1 or introduce additional agents.

## 2. Authoritative inputs
- `../02_patient_data/patient_kb_v1.json`: runtime-safe projection of Synthea evidence, version 1.0, architecture 4.1. Its `patients` array contains ten records. Index by patient_id within source namespace; validate unique IDs and FHIR mapping on startup.
- `../02_patient_data/verified_clinical_registry_v1.json` and original FHIR bundles: provenance and audit sources, not unrestricted runtime retrieval. The projection's clinical cutoff is the selected encounter end.
- Shared Clinical KB: `02_shared_clinical_kb.json` (included in this package). Use versioned rule identifiers, applicability and evidence; do not invent rule IDs or mark absent rules as applied.
- Authorized new clinical events and care plans: optional, timestamped, versioned, provenance-preserving updates. Historical Synthea data remains unchanged.
- Never load simulator physiological configuration, future scenario knots, fault labels, hidden ground truth or training labels into operational patient context.

## 3. Actual source field mapping
| Patient KB field | Context meaning / handling |
|---|---|
| patient_id, fhir_patient_id, source_namespace | Identity; validate against authenticated session and authorized mapping |
| source_is_synthetic, record_version | Source provenance and revision |
| age_at_discharge, gender | Historical demographics; do not infer present age or additional attributes |
| clinical_cutoff, encounter.id/start/end/reason/disposition | Selected encounter and evidence cutoff; null disposition remains unknown |
| conditions[] | Preserve id, label, codes, recorded, onset, abatement, temporal_status, selected_encounter |
| medication_history[] | Preserve id, label, codes, authored, selected_encounter, discharge_use |
| beta_blocker_history[] | Historical prescriptions only; not proof of current use |
| procedures_selected_encounter[] | Preserve id, label, performed and selected_encounter; no inferred surgery |
| historical_vitals | Historical evidence only; not synchronized current measurements or established baseline |
| personalization | spo2_scale, authorized_oxygen_target, hypercapnic_failure_documented, supplemental_oxygen, scale_2_authorized, baseline_status |
| current_medication_use, medication_adherence, allergy_status | Preserve unknown status; never convert unknown into confirmed absence |
| approved_care_plan_ref, assigned_care_team_ref, recovery_phase | Nullable; no invented plan, clinician or recovery stage |
| limitations | Carry relevant source limitations into context and reports |

Source code arrays do not independently establish coding-system metadata. Preserve source codes; resolve system from original FHIR coding or a verified mapping before claiming a standardized code system. An encounter reason is not automatically a confirmed active diagnosis. `no_abatement_documented_by_cutoff` is not proof of active disease; `ended_by_cutoff` indicates historical context, not ongoing illness.

## 4. Retrieval and authorization workflow
1. Accept trusted server-side identity: source_namespace, subject_id, variant_id, session_id, authenticated principal and assessment/source time. Reject blank identifiers and unauthorized requests. Patient ID alone is not authorization.
2. Resolve authorized session and patient mapping; reject mismatch between internal ID and FHIR ID. Do not accept arbitrary patient context from a producer payload.
3. Retrieve indexed patient record. For independent BIDMC replay, use a separate replay subject with explicitly unavailable clinical history; never attach a Synthea profile to a BIDMC record as real patient history.
4. Validate evidence cutoff and record version. Original clinical facts must be available by the selected encounter cutoff; later authorized updates must be available by the assessment time. Reject future information. Use source/physiological time for replay, not wall-clock playback time. Historical timestamps and simulated session time must have an explicit mapping; do not derive recovery days from the current calendar date.
5. Build structured facts with evidence references and statuses. Map clinical domains using versioned, reviewed code/label mappings; preserve unmapped facts and uncertainty. Multiple domains can apply simultaneously. No disease-specific expert replacement.
6. Retrieve Shared Clinical KB rules by domain, fact status, applicability and exclusions. Distinguish applicable, conditional, inapplicable and unknown. Missing KB/rule means unavailable knowledge, not a fabricated rule.
7. Publish immutable context snapshot; cache by full runtime identity plus patient record version, knowledge version and relevant authorized context revision. Refresh on authorized changes, knowledge version changes or time-dependent context changes. No full record retrieval per window. Baseline and live vitals remain independently managed.
8. Pass context reference/version and required fields to downstream consumers. Manifest stores context reference, not full medical history. Ensure all consumers use the same as-of snapshot for a given assessment.

## 5. Clinical interpretation rules
- Preserve documented conditions, historical conditions, suspected conditions, verified procedures and encounter reasons as distinct facts. Do not infer a procedure from a history-of-procedure label, postoperative education or appendicitis encounter.
- MedicationRequest history does not prove dispensing, current use or adherence. Historical beta-blocker evidence may produce a conditional interpretation note about possible blunted HR response, never a numeric score discount or automatic suppression of escalation. Confirmed current use requires separate authorized evidence.
- Oxygen Scale 1 is the default in the current cohort. Scale 2 requires documented hypercapnic respiratory failure and authorized scale selection with valid provenance and applicability. COPD/emphysema alone is insufficient. Preserve supplemental oxygen status separately; unknown must not become room air. The scoring specification will define exact bands and unscorable cases.
- P002-H is a separate synthetic test overlay, not a modification to P002. Load only explicitly authorized test context from a dedicated clinical test fixture in 08_clinical_test_cases.json, not simulator configuration. Require synthetic indication, authorization reference, target and explicit oxygen status for complete test cases. Reject use outside test sessions. Source synthetic status and added hypothetical overlay are separate flags.
- Historical vitals cannot initialize an established stable baseline without eligibility assessment. Baseline engine owns calibration, freeze and adaptation. Context supplies historical references and relevant constraints only.
- Recovery phase, activity restrictions, care plan, allergies and clinician assignment remain unknown unless supported. Do not generate patient instructions from missing plans.
- Unknown discharge destination is not home discharge. A completed inpatient encounter is not evidence of home discharge or medical stability.

## 6. Proposed ClinicalContextV1 logical output
Final field names must be reconciled with the updated V4.1 shared contracts before coding. This example uses real P002 KB identity and facts, but the context ID/session and rule-selection status are illustrative. No rule has yet been executed.

```json
{
  "schema_version": "1.0",
  "context_id": "CTX-P002-DEMO-1",
  "identity": {
    "source_namespace": "synthea",
    "patient_id": "P002",
    "fhir_patient_id": "11e0acc0-192c-5eff-ec24-5da02e77abac",
    "variant_id": "original",
    "session_id": "DEMO-001"
  },
  "patient_record_version": 1,
  "source_is_synthetic": true,
  "hypothetical_overlay": false,
  "clinical_cutoff": "2021-04-22T23:14:19+05:30",
  "selected_encounter_id": "11e0acc0-192c-5eff-1113-eb954c95c949",
  "demographics": {"age_at_discharge": 42, "gender": "male"},
  "discharge_context": {"disposition_status": "documented_home_self_care", "recovery_phase": null},
  "medication_context": {
    "beta_blocker_prescription_history": true,
    "current_beta_blocker_use": "unknown",
    "adherence": "unknown",
    "evidence_refs": ["MedicationRequest/11e0acc0-192c-5eff-628c-1f3080b15c97"]
  },
  "oxygen_context": {
    "spo2_scale": 1,
    "scale_2_authorized": false,
    "hypercapnic_failure_status": "not_documented",
    "authorized_target": null,
    "supplemental_oxygen": "unknown",
    "authorization_ref": null
  },
  "baseline_context": {"initial_status": "not_established"},
  "recovery_context": {"approved_care_plan_ref": null, "assigned_care_team_ref": null, "activity_restrictions": null},
  "knowledge_selection_status": "pending_kb",
  "applicable_knowledge_refs": [],
  "unknown_information": ["current_medication_use", "medication_adherence", "supplemental_oxygen", "recovery_phase", "approved_care_plan", "allergies"],
  "assessment_status": "partial"
}
```
The complete output also includes structured condition/procedure/medication facts with evidence references, clinical domain flags with availability masks, historical reference metadata, context and knowledge versions, source-time/as-of and availability timestamps, limitations, and applicable/conditional rule selections. Do not use this abbreviated example as the full schema. References to original source IDs are provenance references; resolve HAPI resource IDs separately if import changes IDs.

## 7. Downstream behavior and ownership
| Consumer | Context use |
|---|---|
| Four physiological experts | Applicable knowledge, conditional medication effects, recovery context; all four remain active |
| Clinical scoring | Authorized oxygen scale and oxygen status; no arbitrary score modification |
| Baseline engine | Historical references and constraints, not a pre-established baseline |
| Manifest / encoder / PINN-ODE | Context reference and authorized numerical features with masks; no full history in manifest |
| Decision and safety | Evidence-backed patient facts and limitations; independent safety remains active even if context retrieval fails |
| Medication / recovery experts | Approved plans and verified facts; no autonomous treatment |
| Dashboard | Display source facts, unknowns, versions and evidence links; no invented diagnoses |

## 8. Failure and security behavior
Unauthorized or mismatched identity: reject, audit, no cross-patient data exposure. Missing record for an authorized session: explicit context-unavailable status, no fabricated patient facts, deterministic generic safety processing where identity is verified. Missing knowledge: partial context and rule-unavailable status. Never silently reuse a different patient's context. On transient storage failure, use only a previously authorized, identity-matched snapshot if freshness policy permits; mark stale and do not apply expired authorization. Preserve mandatory safety escalation. Audit retrieval, version, authorization decisions and updates without logging unnecessary full medical records.

## 9. Mandatory acceptance tests
| Test | Expected result |
|---|---|
| P001 retrieval | Returns correct FHIR mapping; pneumonia is historical/ended by cutoff, not asserted active |
| P002 retrieval | Historical metoprolol evidence; current use unknown; Scale 1 despite emphysema history |
| P003/P004/P005/P006/P009 | Preserve documented condition and medication evidence; no automatic medication adherence inference |
| P007/P008 | No medication history invented; appendicitis encounter not proof of surgery |
| Unknown disposition | Remains unknown, not home discharge |
| P002-H authorized test overlay | Scale 2 only in isolated test session; original P002 unchanged; oxygen status explicitly represented |
| Unauthorized or wrong FHIR identity | Reject and audit; no patient record returned |
| Independent BIDMC subject | No Synthea medical history attached; missing context explicitly represented |
| Future evidence or future scenario labels | Excluded from operational context |
| Repeated windows | Reuse same eligible context version; no unnecessary full-record reload |
| Authorized context update | New version published; old snapshot reproducible; no retroactive alteration |
| KB unavailable | Explicit partial/unavailable status; independent safety still operates |
| Concurrent sessions/variants | No state or context leakage between identities |
| Context changes interpretation | Same SpO2 input under authorized Scale 1 vs Scale 2 yields different scoring downstream; same HR with historical vs confirmed medication use yields appropriately different evidence interpretation, not arbitrary NEWS2 adjustment |

## 10. Implementation sequence and completion criteria
Implement indexed loader, authorization-aware resolver, deterministic fact mapper, knowledge selector, versioned snapshot/cache and tests. Integrate with existing FastAPI and updated contracts; do not duplicate ingestion or simulator. Demonstrate at least five profiles with relevant conditions and medications and actual downstream context influence. Current candidates P001–P006, P009, P010 have both record types; only P002 and P005 among these have documented home/self-care disposition in this projection. Unknown destination must be disclosed; confirm whether organizers require explicit home discharge and supplement cohort if necessary. P007/P008 do not satisfy the condition-plus-medication demonstration criterion. No implementation completion claim until tests and end-to-end demonstrations run.

## 11. Remaining dependencies
Updated V4.1 shared contracts; Shared Clinical KB and reviewed domain/rule mapping; exact NEWS2 and baseline policies; authorized P002-H clinical test fixture; backend authentication/session mapping and HAPI reference resolution. No additional MATLAB changes are required for this expert. All implementation code must comply with the hackathon's 24-hour rule and organizer AI-assistance policy.
