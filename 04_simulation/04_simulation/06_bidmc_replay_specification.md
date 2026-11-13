# BIDMC replay | canonical data path

## Data actually available
The included independently prepared numeric CSV `bidmc_analysis/replay_numerics.csv` was checked: 53 independent recordings, 25,493 rows, 481 per recording, 1s spacing. Missing HR 4, RR 153, SpO2 128. Record 23 source offsets -1..479; other records 0..480. Preserve source timestamps and recorded missingness. RR zero exists; retain raw zero and flag for quality verification, not a definitive apnea/artifact label. See validation_outputs/bidmc_numeric_verification.json. Original dataset is BIDMC PPG and Respiration Dataset on PhysioNet, version 1.0.0; retain source attribution. The numeric extract is not a new clinical dataset and not derived from the unreadable upload. Raw waveforms are optional; numerical variability does not separate sensor noise from physiology.

## MATLAB source review
`replay/load_bidmc_recordings.m` reads existing numeric extract, checks 53 records/481 samples and continuity. `replay/replay_bidmc_record.m` selects independent recording; `replay/stream_bidmc_to_gateway.m` creates packet log at speed 0 offline, 1 real-time, positive accelerated, optional callback. It is explicitly offline, no network transport. `replay_bidmc_recording.m` older starter generates synthetic TEMP; do not use for canonical BIDMC. `stream_bidmc_to_gateway` uses pause(1/speed) after processing so wall-time drift is possible; use deadline pacing in final shared adapter and measure actual speed.

## Runtime replay
- Each recording separate subject BIDMC-01..53, source namespace bidmc, unique session; no Synthea context, no shared baseline, no linked patient history.
- Map time_s, hr_bpm, rr_per_min, spo2_pct. pulse_bpm is optional additional observation, not automatically HR substitute. No temperature; display unavailable and partial score completeness. Do not fill missing values as measured zero.
- Configure synthetic replay epoch explicitly if original absolute time absent; preserve original offset and actual send time. Record 23 negative offset is legitimate, not invalid freshness. Use elapsed-from-first offset for wall pacing only.
- Send actual R4 Observation through common signed ingestion API. Same safety, clinical scoring and quality logic, isolated simulated alerts and replay dashboard. No real clinical notification; P3 only for offline analytics.
- Preserve all valid abnormal measurements; raw RR zero is a data-quality concern and potentially serious, never silently normal or deleted.
- Run real 1x and accelerated mode (e.g. 10x); verify counts and source offsets independent of wall speed. 481 samples span 480s; do not confuse duration with count. Support stop/reset via unique session IDs.

## Evaluation limitations
Short ICU recordings, not a longitudinal post-discharge cohort; no temperature or deterioration event labels. Use for ingestion, quality, replay, variability and limited forecasting with sufficient history/target span. Do not include as labelled clinical deterioration cases, do not infer true artifact from recorded zero, do not claim clinical validation. 15/30min forecasting cannot be evaluated within an 8min recording; even 5min history + 5min future does not fit without a separately justified shorter history test. No fabricated temperature or patient associations.

## Required proof
One record 13 (zero RR), one record 23 (negative start), all 53 offline packet fidelity, actual 1x/accelerated API receipt and HAPI GET, missing data and isolated replay notifications. Record source vs wall times, event/resource IDs, observed/accepted/persisted counts. Current archive master results unreadable; tests need execution on intact files.
