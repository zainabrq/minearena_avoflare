# MATLAB team handoff | exact remaining requests

## First priority: resend readable artifacts
The uploaded archive's central directory lists 140 files; 26 read successfully and 114 fail ZIP-header validation in this environment. Ask Abhi to verify his local original using archive test or Python `ZipFile.testzip()`, then send smaller separate archives to avoid repeating the issue. No need to regenerate if the local originals are intact.

1. `matlab_source.zip`: source code, configs, README and tests (exclude output.zip, .asv backups and large duplicate outputs). Include MATLAB release/toolboxes, exact entry points, project root handling and version/commit/hash.
2. `batch_training.zip` or split uploads: actual batch_v1 observations.csv, ground_truth.csv, clinical_context.json, run_manifest.json, parameter exports and event annotations. The two listed CSVs are ~142MB and ~162MB uncompressed; compress separately, split by independent run if necessary. Provide per-file SHA-256 and run-level inventory. Do not send only a report.
3. `validation_outputs.zip`: master_test_report_v2.csv, trajectory report, latest integrated observed/truth/fault metadata, joint-probe evidence, actual logs/plots, windowing and quality reports. Include exact source/config versions.
4. Optional `15day_extension.zip`: source and a small actual output sample, model config, duration/cadence, documentation and validation; keep separate from mandatory 1Hz and 40-run batch.

## Required confirmations before backend and AI integration
| Question | Why |
|---|---|
| Which entry point and configuration actually generated each dataset? | Root V1 versus extension V1.1; legacy demo differs from integrated pipeline |
| Are there actually 40 independent runs, ten each stable/deteriorating/transient/recovery? | Master test expects this; verify run manifest and data |
| What are exact row counts, run durations, source interval and seed per run? | Forecast horizon, split and reproducibility |
| Are true fields exported before sensor noise/artifacts and separately from target knots? | Avoid treating scenario target as true state |
| Is joint SpO2 dropout/zero plus HR flatline implemented in integrated flow? | Mandatory PS03; existing readable test uses separate RR removal and SpO2 flatline |
| Are motion and true sudden spike different scenarios? Is connectivity actual packet loss or all-null? | Artifact and safety evaluation |
| What are actual onset, end and severe endpoints for deterioration? | Lead-time evaluation; independently label from truth |
| Are batch runs varied by seed, onset, severity, initial state and parameters, and not just repeated copies? | Prevent leakage and insufficient diversity |
| What exact math runs in batch and 15-day extension, and which external inputs are known at forecast origin? | PINN-ODE mathematical handoff |
| Can MATLAB callback/export provide ordered source rows with identity, sequence and quality? | Shared Python adapter handles FHIR and signing |
| Is 15-day extension intended as a separate low-rate experiment or actual 1Hz trajectories? | Duration/size, separate evaluation and avoid unsupported claim |

## Priority ownership
Abhi/MATLAB: healthy source, actual data/metadata, run commands, independent truth and tests; fix joint probe if missing. AI team: approve equations/parameter bounds, exact encoder semantics, grouped splits, train/calibrate, report actual results. Backend/Claude: common Python adapter, FHIR ingestion and storage, authentication, replay scheduling/acceptance evidence, clinical gateway and state isolation. Clinical/integration lead: preserve V1.1 patient data, approve scenario labels and clinical context, review safety. Do not ask MATLAB to implement NEWS2, clinical experts, PINN-ODE or full JWT/HMAC transport separately.

## Ready-to-send message
Abhi, your archive shows the structured MATLAB simulator, batch generator and 15-day extension. I could inspect the physiology/sensor/replay/test source, but the uploaded ZIP has unreadable local entries, including the batch CSVs and reports. Please test your local ZIP and send source, batch data and validation outputs as separate smaller archives with hashes. Please include exact MATLAB release, commands/config version, actual independent run counts/durations/seeds and the full observations/truth/context/run manifest. Confirm the integrated joint probe removal test (SpO2 null or zero AND HR holds last valid pre-event reading while true physiology continues), separate motion vs genuine spike, actual connectivity gap, and event onset/end/severe endpoint labels. Your readable master V2 checks 40 runs and separate sensor faults; we need the actual report and joint test evidence. Also clarify the 15-day extension cadence and equations, and whether batch logic is interpolation+AR(1) or actual coupled ODEs. No need to regenerate the entire dataset if existing files pass. Claude will handle FHIR conversion and security; provide the observed stream/callback and metadata. Keep V4.1 architecture unchanged.
