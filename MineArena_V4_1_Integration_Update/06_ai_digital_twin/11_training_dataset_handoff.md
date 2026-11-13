# Unified offline dataset and team handoff
Based on teammate training handoff; exact formats proposed, existing exports mapped by adapter. No actual training data generated here. Preserve original MATLAB files and offline ground truth access restriction. Suggested root `04_simulation/training_batches/<run_id>/`; derived datasets and artifacts under `06_ai_digital_twin/training_data/` and `artifacts/`, not runtime API. One immutable run ID and full identity key per trajectory.

| File | Required contents / keys |
|---|---|
| observations.csv | run_id, patient/subject, session, variant, source_time_s, sequence, per-vital observed value/unit/quality/missing reason, original observation ref; native sample resolution |
| ground_truth.csv | run_id/source_time_s, true HR/RR/SpO2/T before artifacts, label availability; offline only |
| run_manifest.json | run_id, seed, simulator version, cadence, duration, scenario type, onset/end/severe endpoint, artifact intervals, context ref, parameter version; offline only; alias scenario_manifest.json |
| physiological_parameters.json | actual generator equations/interpolation, parameters, units, bounds, initial states, known/hidden external inputs, version |
| artifact_events.csv | run_id, start/end source time, type, affected vitals, labels offline |
| clinical_context.json | immutable context snapshot as of source time, patient context API output; preserve unknowns |
| expert_features.parquet / expert_evidence.jsonl | per-frame 32 features + masks and original evidence refs, clinical rule versions |
| baseline_states.parquet / clinical_scores.parquet / signal_quality.parquet | causal per-frame state, eligibility, coverage, previous baseline, freeze and rule refs |
| physiological_manifests.jsonl | same runtime builder, fixed 15s assimilation checkpoints; no labels |
| encoded_frames.parquet | 264 values, key/frame refs, registry/normalizer version, availability |
| split_registry.json and train/validation/test sequences | group whole runs first, history and future target masks, no overlap across splits |
| forecast_evaluation.parquet / uncertainty_calibration.json / counterfactual_results.parquet | actual held-out predictions/errors/intervals, branch assumptions, calibration and versions |

Use actual CSV/JSON/Parquet equivalents; schemas and joins versioned, hashes and quality checks. No duplication of source files unnecessary. Ground truth and scenario labels accessible only to offline training/evaluator, never manifest/encoder input. Clinical context snapshots from Patient Context API at cutoff; no future diagnoses. Training history 5min proposed, primary future 5min; 15/30min only adequate trajectory length. Separate BIDMC evaluation. Start with diverse stable/deteriorating/recovery/activity/artifact/mixed cases, independent seeds and parameter variation; 800 runs optional planning, verify actual run lengths and count before scaling. MATLAB team delivers raw/true/scenario/parameters and actual equations; clinical team provides existing 03 specs and runtime implementations; AI team approves exact 264 registry and equations, trains and calibrates; integration team supplies shared contracts/source adapter, tests and evidence. Do not claim 30,310 observations sufficient without actual audit.
