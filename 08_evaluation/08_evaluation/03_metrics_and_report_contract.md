# Metrics and report contract v1.0
All metrics are actual measured engineering results only. Never report simulated examples as measured outcomes.

| Metric | Definition |
|---|---|
| Detection lead time (s) | severe_endpoint_s - first qualifying alert source_time_s; positive earlier, negative late. Report median/mean and n among detected events with endpoint. |
| Detection delay (s) | first qualifying alert source_time_s - onset_s; report separately for all detected events. |
| Detection rate | matched deterioration events / total labelled deterioration events; show counts. |
| Missed events | total labelled deterioration events minus matched events. |
| Paired lead improvement | proposed lead minus comparator lead for same event detected by both; report n and missed events separately. |
| False clinical alerts | unmatched clinical episodes; report stable and artifact-only subsets. |
| Clinical alerts per patient-day | unique clinical episodes / (sum monitored source seconds / 86400). |
| Technical and verification burden | unique episodes of each category per patient-day; report total unique episodes without double counting overlapping categories. |
| Artifact detection precision/recall | TP/(TP+FP), TP/(TP+FN) for predeclared sample-level fault labels, per vital, with coverage; optionally episode-level matching separately. |
| FHIR compliance | accepted valid stored observations / expected valid observations; report resource validation failures, persistence failures, missing expected resources and retrieval evidence separately. |
| Explainability completeness | qualifying clinical alerts with actual reading/ref, rule/version and relevant patient fact/ref (or explicit unavailable context) / qualifying alerts; separately count alerts with genuine profile evidence and generic rules. |
| Latency | p50/p95/p99 of measured durations; report n, hardware, concurrency, playback speed and failures. |

Zero denominators => null/not applicable, not zero. Report source seconds per run using declared monitoring interval [start,end), including planned connectivity gaps; report connected/valid coverage separately. No double-counting overlapping intervals of same session. Do not use wall time as exposure. Report small-sample limitations and per-scenario results; no real clinical conclusions. Alert suppression must retain detection rate and expose verification burden.

## Timing instrumentation
Record source_time_s, measurement wall timestamp, receipt monotonic time, safety decision, window close, routine decision, forecast frame available and completion, dashboard publication and optional client receipt. Use synchronized wall clocks for cross-host measurement-to-receipt, or report only valid same-clock durations; do not subtract unrelated monotonic clocks. For accelerated replay distinguish physiological time from transmission wall time. Targets from policy 07: sampled event to safety notification <2s, routine after window close <1s, forecast after eligible frame <2s. Report misses/timeouts separately and percentile method (e.g. linear quantile). Do not claim these are clinically validated deadlines.

## Required output tables (CSV or JSON)
- run_summary: run_id, patient/subject, variant, duration_s, source, seed, split, scenario_id, policy_version, comparator_version, model_status, observation_count, valid_coverage, error_count.
- event_results: run_id, event_id, system, onset_s, severe_endpoint_s, end_s, detected, episode_id nullable, first_alert_s nullable, lead_s nullable, delay_s nullable, preexisting_alert, evidence_refs.
- alert_episodes: system, run_id, episode_id, category, initial_priority, maximum_priority, opened_s, resolved_s nullable, matched_event_id nullable, false_clinical, artifact_overlap, notification_count, evidence_refs.
- fhir_validation: source, run_id, event_id, observation_id, code, valid, persisted, retrieved, error_reason.
- latency_samples: run_id, event_id, stage, elapsed_ms, timing_basis, concurrency, playback_speed, outcome.
- aggregate_metrics.json: schema_version, evaluation_id, policy/config versions, run_ids, exposure_seconds, per_system metrics, paired metrics, per_scenario breakdown, warnings, raw_artifact_paths. Store null for unavailable metrics.

## Optional model evaluation
If PINN-ODE is implemented: compare persistence, linear trend, mechanistic ODE, unconstrained neural ODE and hybrid on same held-out valid targets and forecast origins. Report per vital/horizon MAE/RMSE, interval coverage/width, abstention fraction, solver failures and latency. 5 min primary, 15/30 secondary only where data duration supports them. BIDMC has no temperature or labelled post-discharge events; only limited forecasting/replay assessment. Do not conflate forecast accuracy with clinical detection improvement. Clinical ablation must retain same safety rules, no experimental prediction-driven escalation.
