# Simulation validation and acceptance tests

These are expected checks, not executed results. Save actual outputs under validation_outputs/ with source/config hashes, MATLAB release, commands, seed, run IDs, timestamps, expected vs actual, pass/fail and artifact references. Current verified outputs: archive inventory and BIDMC structural check only. Do not mark clinical performance based on simulator unit tests.

| ID | Test | Acceptance |
|---|---|---|
| S01 | Archive integrity | all file entries readable, CRC pass, no nested duplicate archive needed |
| S02 | Configuration | V1.1 exact original 10 mappings match patient registry; P002-H separately scoped |
| S03 | Reproducibility | same seed/config reproduces same numerical data; distinct seeds vary appropriately |
| S04 | Independence | one patient's fault/state does not change another's truth or random stream |
| S05 | True/observed join | unique run/time keys, same identity, finite truth, missingness preserved |
| S06 | Stable | stable target with AR variability; no hidden deterioration label |
| S07 | Gradual deterioration | independent true onset/end/severe endpoint, trend visible; no fixed-onset leakage |
| S08 | Genuine sudden spike | true physiological change distinct from sensor spike, evaluate safety |
| S09 | Motion | observed perturbation only, underlying truth unchanged vs matched seed/no-fault run |
| S10 | Required joint removal (null) | same interval SpO2 missing + HR held at last valid pre-removal observed value; truth continues |
| S11 | Required joint removal (zero) | same as S10 but recorded SpO2 0 preserved; evaluate quality, not substitute null |
| S12 | Genuine deterioration plus fault | both labels independent, remaining reliable signals continue; no safety suppression |
| S13 | Intermittent missing | channel-level gaps preserved, recover after scheduled fault |
| S14 | Connectivity | actual packet absence/sequence gap differs from all-null packet; no false recovery |
| S15 | Calibration | deterioration before 900s; independent safety not waiting for clinical baseline |
| S16 | Recurrence | critical-normal-critical; evaluation records distinct intervals and unresolved episode behavior |
| S17 | Scale 2 test | P002-H isolated approved hypothetical context, identical 91% compared against Scale 1, oxygen status explicit |
| S18 | Batch diversity | actual counts/durations/seeds by patient/scenario; no duplicate/overlapping train-test runs |
| S19 | Batch target horizon | adequate source history and future truth; no interpolation beyond target availability |
| S20 | BIDMC fidelity | 53 records, 25,493 rows, 481 each, source offsets and missing counts, no temp |
| S21 | BIDMC zero/offset | record13 RR zero preserved; record23 starts -1; no false timestamp rejection |
| S22 | Replay pacing | 1x and accelerated actual source/wall duration, no hidden loss, cancellation/reset |
| S23 | Native FHIR | MATLAB + BIDMC actual API acceptance and HAPI GET with correct code/unit/reference |
| S24 | Retry and security | identical retry exactly once; invalid signature/replay/identity blocked |
| S25 | Concurrent streams | ten patient/session states isolated; per-session ordering, no cross overwrite |
| S26 | Gateway timing | event safety immediate; adaptive 5/10/15s only routine, fixed 15s encoder, no lost samples |
| S27 | FHIR outage | accepted hot-path processing continues, persistence recovered idempotently |
| S28 | UI device state | authorized confirmed simulated removal only; suspected/connectivity distinct, no labels into model |
| S29 | Ground-truth leakage | runtime payload and encoder contain no future targets, scenario/fault truth or patient ID feature |
| S30 | Optional 15-day extension | inspect cadence, parameters and outputs; verify labels and source time before use, no claim required for PS03 |

## Evidence review of existing master V2
Readable `tests/run_minearena_master_tests_v2.m` has six groups: initialization, 40 batch trajectories, sensor faults, 53 BIDMC replay, packets and fixed windows. Its sensor test asserts HR motion, SpO2 flatline, RESP probe removal, all-null connectivity, intermittent temperature missing and five recovery records; does NOT assert combined SpO2 removal/HR flatline. Its batch check asserts 10 per type and 40 overall, but only target range/classification; new independent CSV join/seed checks needed. Its report in uploaded copy is unreadable. Run it on intact archive, then run the new cases above. Do not treat old output filenames or a screenshot as proof.

## Joint-probe test procedure
Create matched-seed stable control and removal run. At t=3000..3029 (existing P010 nominal schedule, or explicit new start), SpO2 null/zero according to variant, HR held from last valid observed sample at t=2999. At t=3030 release hold. True HR/SpO2 and remaining true signals match no-fault control given identical physiology stream; no change in true values caused by sensor. Include genuine deterioration counterpart with independent labels, and reliable RR/TEMP continuing. Compare output columns and plot around event. Export observed, truth, fault intervals and status, but only observed measurements enter runtime. If existing run shorter, choose separate scheduled interval documented with actual start/end. Existing eight-minute default replay does not cover t=3000.

## Actual report format
Record test_id, result (PASS/FAIL/BLOCKED/NOT_RUN), code/config hashes, run_ids, commands, environment, expected, actual, evidence files, failures, owner, timestamp. Never fill PASS without execution or explicit source-only check. Clinical evaluation uses 08_evaluation's comparator and event annotations, not these unit test expected values.
