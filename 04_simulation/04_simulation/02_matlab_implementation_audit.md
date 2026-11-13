# MATLAB implementation audit | uploaded handoff

## Evidence boundary
Reviewed archive `Abhi_MATLAB_Virtual_Wearable_Simulator (2).zip` (193,868,425 bytes). Central directory: 175 entries including directories, 140 files. 26 files successfully read with CRC check; 114 fail local ZIP header validation (`Bad magic number for file header`). The failing entries have non-ZIP local header bytes in the mounted copy. This establishes unreadability of this copy, not corruption of Abhi's original local file. See validation_outputs/upload_archive_inventory.json for exact file-level status. No MATLAB runtime execution was performed.

## Findings
| Component | Evidence | Status / required action |
|---|---|---|
| Patient configuration | profiles/load_physiological_config.m validates fields, exact ten patients and FHIR matches | Code inspected; actual run not verified; explicitly select V1.1 and handle overlay separately |
| Independent physiology | physiology/initialize_physiological_state.m uses independent per-patient physiology/sensor streams; generate_correlated_physiology.m and interpolate_scenario_targets.m readable | Verified source design: piecewise linear target + per-channel AR(1), not mechanistic ODE or cross-channel covariance |
| Sensor effects | sensor/apply_configured_sensor_effects.m | Independent Gaussian sensor noise, per-channel random missingness, configured probe-removal and connectivity NaN supported; other types raise unsupported error |
| Additional sensor scenarios | sensor/apply_sensor_fault_scenarios.m | Motion, flatline, probe removal, connectivity and intermittent missingness implemented in separate function; integrated invocation unverified because evaluation source unreadable |
| Joint required probe fault | test_sensor_fault_scenarios.m; tests/run_minearena_master_tests_v2.m | Tests separate SpO2 flatline and RESP removal; not the mandatory simultaneous SpO2 null/zero + HR hold. Add dedicated joint test and integrated export |
| Batch generator | batch/generate_training_batch.m listed, unreadable | Cannot verify actual generation, duration, seeds, parameter variation or run counts |
| Batch CSVs | output/batch_training/batch_v1/observations.csv (142,156,947 bytes), ground_truth.csv (162,141,181 bytes), clinical_context.json, run_manifest.json | All unreadable. File sizes/listings not evidence of content or data quality. Re-export or send separately |
| Batch validation | validation/validate_batch_trajectories.m readable | Checks run labels, target ranges and exact 40 runs/10 per class; no observed/truth join, duplicate check, seed independence or complete trajectory semantics |
| Master V2 tests | tests/run_minearena_master_tests_v2.m readable; output/master_validation_v2/master_test_report_v2.csv listed unreadable | Six groups defined: 10 initializations, 40 batch runs, sensor fault tests, all 53 BIDMC replay/packets/windows. Cannot confirm passed |
| Integrated outputs | latest integrated_observed_20261112_200229.csv, integrated_ground_truth_20261112_200229.csv, integrated_fault_metadata_20261112_200229.csv listed | Actual data unreadable; cannot confirm P010, 30,310 rows, duplicates, durations or signal quality. Do not count repeated timestamped files as independent runs |
| Adaptive windows / quality | gateway/adaptive_window_controller.m, create_observation_windows.m, gateway_data_quality_monitor.m and reports listed unreadable | Presence only; validate against backend authoritative adaptive policy, not two competing implementations |
| Real-time simulation | run_minearena_realtime_replay.m readable | Deadline-paced, ten-patient per-tick table, optional callback. Dry run if no callback. `api_transmission_performed=false` even in callback mode; actual receipt needs independent evidence |
| HTTP posting | send_observation_to_gateway.m | webwrite raw application/json, optional single auth header, catches errors with warning; no final FHIR, HMAC, JWT refresh, idempotency or verified persistence. Default gateway disabled |
| BIDMC | replay/load_bidmc_recordings.m, replay_bidmc_record.m, stream_bidmc_to_gateway.m readable | offline packets and optional callback, source timestamps and values preserved, no TEMP in newer adapter. Actual FHIR transmission unverified |
| Legacy BIDMC | replay_bidmc_recording.m | Generates synthetic TEMP and custom JSON; do not use this path for canonical real-data replay |
| Longitudinal extension | MineArena_15Day_Extension/longitudinal/generate_15day_patient_data.m, generate_post_discharge_targets.m, post_discharge_model_v1.json, training/build_15day_training_dataset.m, validation/validate_15day_dataset.m and README_FIRST.txt listed unreadable | Cannot confirm model, cadence, duration, labels or exports. Optional until reviewed; not replacement for 1Hz batches |

## Other technical gaps visible in code
- Master V2 default path and test_sensor_fault_scenarios.m hardcode `D:\Abhi_MATLAB_Virtual_Wearable_Simulator`; pass project root explicitly and replace hardcoded test path with parameter/relative path in a reviewed patch.
- Master V2 expects config V1, exactly ten patients and exactly forty runs. Preserve old reproducibility but create a generalized validator for V1.1 and any larger batch.
- Fault schedule helper uses `fault_type`, while config layer uses `type`, `channel`, `observed_value`; normalize through a documented adapter. The scheduled flatline captures the first observed value at fault start; required joint test should hold last valid pre-removal HR, with fallback unknown if absent. Connectivity all-NaN is not equivalent to absent packets; test actual suppressed transmission separately.
- `generate_correlated_physiology` marks calibration complete/frozen based only on elapsed time. Backend clinical baseline is independent and eligibility-driven; simulator calibration metadata must not drive clinical decisions.
- Repeated integrated output filenames and sizes are not proof of independent runs. Compare hashes, run IDs, seed/config combinations, and full trajectory data.

## Recommended release gate
Clean archive and manifest -> exact execution commands -> reproduce tests -> joint probe test -> read and audit existing 40-run batch -> evaluate adequacy for five-minute model -> add missing diverse runs only -> secure FHIR end-to-end test. Do not request wholesale regeneration if actual existing dataset passes.
