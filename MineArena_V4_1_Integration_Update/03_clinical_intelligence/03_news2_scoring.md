# Partial NEWS2 scoring and oxygen personalization

**MineArena PS03 | Frozen Architecture V4.1 | Specification v1.0**

Engineering prototype only; clinical decision support, not diagnosis. Implementation, integration and clinical validation pending. All numeric timing and decision heuristics below are configurable engineering defaults, not clinical guidelines. Do not add architecture components or use SNN.

## 1. Authoritative scoring reference
Royal College of Physicians, NEWS2 observation chart, December 2022: https://www.rcp.ac.uk/media/eczf5mvm/news2-chart-3_news-observation-chart_2022_0_0.pdf. This specification implements only four component scores, not the complete NEWS2 system. RCP escalation thresholds must not be applied to the partial subtotal. Do not display a risk probability. Adults only; pediatric/pregnancy applicability requires separate review. All cohort records are synthetic; no clinical validation implied.

## 2. Input and normalization
Use authenticated session identity, as-of context version, assessment timestamp, original observation reference, canonical units, quality and age. HR and RR `/min`, SpO2 `%`, temperature `Cel`. Reject incompatible units or nonfinite values; valid explicit conversion must retain original. Select latest observation per vital at or before assessment time, max age 15 source seconds (engineering default); never carry a stale value forward as current. If latest is missing/suspect/invalid, do not replace with an earlier valid value for current scoring. Preserve historical value separately. Score valid values only. Raw zeros remain auditable; zero HR/RR/SpO2 are suspect until verified, not normal; 07 handles urgent verification. Verified zero HR/RR is an emergency concern, not a normal scored measurement. 

For reproducibility use decimal round-half-up to nearest integer for HR/RR/SpO2, nearest 0.1 Celsius for temperature, only after checking raw validity and bounds. This is a prototype discretization choice, not an RCP rounding mandate. Safety checks also inspect raw values; rounding must not conceal concerning values. Store raw and scored value. Bands below inclusive.

| Vital | Score bands |
|---|---|
| HR | <=40:3; 41–50:1; 51–90:0; 91–110:1; 111–130:2; >=131:3 |
| RR | <=8:3; 9–11:1; 12–20:0; 21–24:2; >=25:3 |
| SpO2 Scale 1 | <=91:3; 92–93:2; 94–95:1; >=96:0 |
| Temperature | <=35.0:3; 35.1–36.0:1; 36.1–38.0:0; 38.1–39.0:1; >=39.1:2 |

## 3. Scale 2 (personalization rule 1)
Select Scale 1 by default when no valid Scale 2 authorization exists. Require documented hypercapnic respiratory failure, qualified clinician authorization reference and effective interval, target 88–92, and matching patient/session context. Do not infer from COPD, emphysema or acute respiratory failure alone. Expired or revoked authorization falls back to Scale 1 with context warning; no autonomous oxygen changes. P002-H is isolated synthetic fixture in file 08, never edit P002 original.

| Rounded saturation | Scale 2 score |
|---|---|
| <=83 | 3 |
| 84–85 | 2 |
| 86–87 | 1 |
| 88–92 | 0 |
| >=93, room air | 0 |
| 93–94, supplemental oxygen | 1 |
| 95–96, supplemental oxygen | 2 |
| >=97, supplemental oxygen | 3 |
| >=93, oxygen status unknown | null / unscorable |

Unknown oxygen status at <=92 does not change the Scale 2 component band, but remains an explicit limitation. Separate oxygen +2 component of full NEWS2 is excluded. High saturation on oxygen does not automatically mean hypoxemia; escalation interpretation uses actual direction and authorized context (07).

## 4. Output contract (logical; reconcile Pydantic names)
ClinicalScoreV1 contains identity/context version, assessment_at/source time/state version, each component raw value, scored value, unit, score|null, eligibility status/reason, observation refs and rule ID/version; oxygen scale, authorization ref, oxygen status; observed_subtotal=sum of scored components or null if none; scored_count; maximum_available_subtotal=3*scored_count; theoretical_maximum=12; full_news2_score=null; missing_or_unscorable list; status complete_four/partial/unavailable/failed. No score for predicted or imputed physiology. Do not compare subtotals across different coverage without coverage labels.

## 5. Example acceptance checks
HR=108, RR=26, SpO2=92 Scale1, Temp=38.1 => 1+3+2+1=7/12 (not a full NEWS2 threshold). Same HR/RR/temperature and SpO2=91: Scale1 component 3 versus authorized Scale2 component 0. Scale2 at 96 on oxygen=2; on air=0; unknown=null. Missing temperature gives three scored components and maximum available 9. All unavailable gives null subtotal, not zero. At 35.0 temperature score 3. See file 08 for boundary cases. Baseline and medication context influence interpretation/alerts, not published component bands.


## V4.1 integration revision (Backend V1.1)
Add `maximum_component_score = max(eligible component scores)` or null if none. Keep existing `observed_subtotal` (partial_news2_subtotal logical alias) and coverage fields, do not double-count or add age points. Example 2+2+2+1 = 7, max=2. Maximum is supplementary routing evidence, not the sole clinical assessment. Missing and suspect scores remain unavailable; maximum over eligible scores may be lower than true unknown maximum, so label coverage. No automatic P0 from age or upper Scale2 score alone.
