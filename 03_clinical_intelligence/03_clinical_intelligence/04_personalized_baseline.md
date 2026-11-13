# Personalized rolling baseline

**MineArena PS03 | Frozen Architecture V4.1 | Specification v1.0**

Engineering prototype only; clinical decision support, not diagnosis. Implementation, integration and clinical validation pending. All numeric timing and decision heuristics below are configurable engineering defaults, not clinical guidelines. Do not add architecture components or use SNN.

## 1. Purpose
Personalization rule 2: identify gradual deviations from an individual's stable reference. Baseline is a monitoring reference, not a diagnosis or safe target. Separate per vital and full runtime identity (namespace, subject, variant, session). BIDMC independent; no Synthea baseline transfer. No scenario targets, simulator ground truth or forecasts as observations. Historical KB values are evidence only unless individually verified stable and eligible; default cold start.

## 2. Deterministic V1 policy
All durations use source time, not replay wall time. Defaults: calibration 900 eligible seconds, trailing reference 1800 seconds of eligible observations, freshness 15s, coverage >=80% of expected samples in each 30s eligibility block, no gap >2 nominal intervals for continuity. Expected rate from authorized source metadata. Calibration requires 900 elapsed source seconds in a contiguous eligible segment; gaps or ineligible blocks break segment; no summing disconnected samples to claim stability. At 1Hz, require >=720 valid samples within 900s, with gap limit. Evaluate per vital, but freeze all on any clinical concern. Require adult eligible context, reliable valid values, no active clinical alert or unresolved verification, no reported acute symptoms or known activity transition, stable clinically applicable score (zero or explicitly clinician-approved stable reference), no candidate deviation or suspicious trend. Unknown activity is recorded, not assumed rest; prototype can calibrate when no contradictory evidence and coverage criteria met, with limitation. If no eligible baseline, still run safety/scoring.

Reference = median eligible values; dispersion = median absolute deviation (MAD); robust scale=max(1.4826*MAD, floor). Floors HR 1 bpm, RR 1/min, SpO2 0.5 percentage point, Temp 0.1 C. Keep previous reference before evaluating new measurements. Report delta=latest-baseline and robust_z=delta/scale. No z-score if absent baseline. Reference updated after assessment only on eligible stable blocks, using trailing eligible samples; do not backfill future values. At calibration completion publish first baseline; never retrospectively alter prior assessments.

## 3. Deviation defaults (prototype, not diagnostic)
| Vital | Candidate absolute deviation | Additional criterion |
|---|---|---|
| HR | abs(delta)>=15 bpm | robust abs(z)>=3 |
| RR | abs(delta)>=4/min | robust abs(z)>=3 |
| SpO2 | delta<=-3 percentage points | robust abs(z)>=3 |
| Temp | abs(delta)>=0.5 C | robust abs(z)>=3 |
Candidate triggers baseline freeze and short-window monitoring; persistence/clinical escalation determined by 07. Evaluate latest valid values, not window averages alone. Trend slope uses 05. Lower HR/RR and falling temperature can also be concerning. Use both magnitude and scale to reduce noise-driven triggers; no guarantee of clinical sensitivity. Sensitivity analysis required.

## 4. State transitions
unestablished -> calibrating -> established; freeze on candidate deviation, score >=2, clinical Review/Urgent, suspect data, unresolved safety verification or interrupted monitoring. A single suspect vital freezes its own baseline; clinical concern freezes all. During freeze preserve last eligible reference and evidence; no adaptation to deterioration. Unestablished baseline remains unestablished/frozen if concern arises. Resume only after 60s continuous eligible stable observations, no active safety/clinical alert, valid recovery evidence and required clinician closure. Missing or suspect data resets recovery timer; a normal packet does not clear alert. If reference absent, restart calibration; if old reference invalid after authorized clinical context change, retire version and recalibrate. No baseline reset just to make deviations disappear.

## 5. BaselineStateV1 logical output
Identity, vital, context_version, status, baseline_value|null, dispersion_mad|null, robust_scale|null, unit, sample_count, coverage, eligible_duration_s, calibration_progress, source interval, last_eligible_at, frozen boolean, freeze_reason, version, policy_version, evidence_refs, last_update_at. Reference must be available as-of assessment; publish new version only after decision. Retain previous versions for replay. Persist independently of manifest and restart; restore by exact session identity only.

## 6. Tests
Stable 900s -> establish; 899s -> not established; missing gaps -> no false eligibility; slow HR drift from 65 to 87 -> candidate before fixed HR boundary if dispersion permits; freeze before updating; no drift into new normal; missing during recovery resets timer; two patients cannot share state; simulator target changes must not modify runtime baseline directly. See 08.
