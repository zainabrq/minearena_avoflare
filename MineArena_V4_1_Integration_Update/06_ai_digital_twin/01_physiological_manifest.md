# Textual physiological state manifest
Authoritative V4.1 sections 6, 8. Manifest is deterministic structured JSON; no model training for builder. It represents reconstructable virtual physiology, not a patient biography, picture, clinical diagnosis or simulator labels.

## Required logical contract
| Field | Semantics |
|---|---|
| manifest_id/schema_version/state_version | Unique versioned state; monotonic per runtime key |
| identity | source_namespace, patient/subject ID, variant, session; opaque only |
| source_time_s/created_at | Causal physiological cutoff and wall publication UTC |
| context_ref | Immutable ClinicalContextV1 reference, not copied clinical history |
| observed_state | HR/RR/SpO2/temp, raw/scored eligible value, units, time, quality, original observation refs; missing null |
| baseline_state | Per-vital previous eligible baseline/spread/status/freeze/version and refs |
| physiological_relationships | Applicable hypothesis/supported relationship IDs, status, evidence and knowledge versions |
| model_configuration | Equation set and parameter profile refs, provisional/approved applicability |
| expert_evidence_refs | Four expert results, deduplicated underlying evidence refs |
| uncertainty | Measurement, missingness, parameter/context/baseline limitations |
| estimated_state_ref/checkpoint_ref/parent_manifest_ref | Reconstructable computational state and immutable lineage; may be unavailable before model |

Keep detailed patient history and clinical facts in context service. Parameter priors/estimated parameters are versioned refs or typed virtual numeric values, not copied medical records. No future observations, scenario ID/onset/label, ground truth, known simulator parameter targets unavailable at runtime, or images. Separate offline run_manifest.json from physiological manifest.

## Causal builder
At each fixed 15s source boundary, take only events available by cutoff (use defined watermark, arrival eligibility and deterministic replay policy), previous eligible baseline, same context version and four expert outputs; never interpolate from future. Adaptive 5/10/15s window decisions do not change frame timeline. Build/update manifest on accepted evidence as V4.1 permits, emit fixed assimilation frames separately; exact initial boundary t=0 policy explicit. Snapshot uses full runtime key and compare-and-swap version, immutable input for model job. Canonical serialization/hash, parent chain and reproducibility check; no claim of tamper-proof without protected audit anchor. Late event stored historical, not overwrite current state; optional offline reconstruction separately labelled. Model estimated output references committed only if still current; no circular feature dependency on same-frame future result. Counterfactual branch copies immutable manifest with branch ID; no canonical state mutation.

## Tests
Same ordered events/context/rule versions produce same semantic manifest hash (exclude wall-time nondeterminism from semantic hash). No future data, cross-key state or raw patient history; unavailable context/baseline retained; source-time offsets correct; all four experts referenced even when unavailable. Checkpoint reconstruction and stale model result rejection. Use same builder for historical training and runtime; offline labels joined only after feature generation.
