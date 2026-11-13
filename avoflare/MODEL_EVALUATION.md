# How the Avoflare models work, and how they performed

Synthetic data (10 patients x 15 days, simulator ground truth). Every score below comes from a model that never saw that patient (leave-one-patient-out). Engineering evaluation, not clinical validation. Source: `results/model_evaluation.json`, `results/evaluation_metrics.json`, `results/twin_report.json`.

## 1. The three layers and what each does
| Layer | What it is | Role in a decision |
|---|---|---|
| Safety + clinical rules | Partial NEWS2 (HR, RR, SpO2, Temp), personal baseline (median/MAD), persistence, artifact checks, SAFE/CLIN rules | Decides Watch / Review / Urgent. Always runs, no model dependency |
| Continuous risk model | Gradient-boosted trees on 44 expert features every 10 s | Score >= 0.90 for 30 s raises a patient to Review (ML-1). Can never lower a priority or create Urgent |
| Digital twin (PINN-ODE ensemble) | Relaxation to personal baseline + HR temperature/activity coupling + neural residual, 4 members, RK4 | 5/15/30 min forecasts with calibrated 95% band. Displayed only; cannot change priority |

## 2. Overall results
| Measure | Fixed NEWS2 | Rules | Rules + model |
|---|---|---|---|
| Deteriorations detected | 9/9 | 9/9 | 9/9 |
| False alerts per patient-day | 142 | 8.8 | 9.1 |
| Median time to first alert | 205 s | 769 s | 359 s |
| Minimum warning before severe | 9.4 min | 5.7 min | 5.7 min |

Risk model alone (10 s windows): AUROC 0.961 (95% CI 0.903-0.992), AUPRC 0.824 at 0.5% prevalence, precision 0.96 at the operating threshold.

## 3. Event by event (seconds after onset; "lead" = warning before severe)
| Patient | Scenario | NEWS2 | Rules | Model | Combined | Severe at | Lead |
|---|---|---|---|---|---|---|---|
| P001 | gradual respiratory | 748 | 1118 | **918** | 918 | 2787 | 31 min |
| P002 | transient respiratory | 38 | **218** | 478 | 218 | 606 | 6.5 min |
| P003 | heart-failure pattern | 205 | **745** | 895 | 745 | 1905 | 19 min |
| P004 | sudden cardiovascular | 38 | **48** | 188 | 48 | 892 | 14 min |
| P005 | muted HR response | 559 | **769** | 779 | 769 | 2595 | 30 min |
| P006 | episodic respiratory | 3 | **223** | 333 | 223 | 564 | 5.7 min |
| P007 | fever deterioration | 2351 | 5411 | **4581** | 4581 | 16532 | 3.3 h |
| P009 | complex cardiac | 404 | 774 | **404** | 404 | 2853 | 41 min |
| P010 | respiratory + probe fault | 54 | 1134 | **824** | 824 | 2916 | 35 min |
| P008 | stable recovery | no event | | | | | |

How to read it: the rules catch sudden and fast changes first (P002, P003, P004, P006); the model catches slow drifts first (P001, P007, P009, P010), 3 to 14 minutes earlier than the rules. Fixed NEWS2 is often first, but only because it alarms almost continuously (142 false alerts a day).

## 4. What the model relies on (permutation importance, drop in AUPRC)
1. SpO2 5-min median vs personal baseline (0.015)
2. Temperature 5-min change vs 30 min ago (0.015)
3. Temperature value (0.008)
4. Temperature 5-min median vs baseline (0.007)
5. Heart-rate value, exertion context, HR 30-min drift (about 0.001 each)

By group: slow-drift features (5 vs 30 min) 0.039, temperature 0.030, SpO2 0.015, HR 0.003, RR under 0.001. The model has learned slow multi-vital drift, which is exactly what the rules are weakest at. RR adds little because the rules already handle RR well.

## 5. Calibration
Scores 0.9-1.0: 95% of those windows are real deteriorations, so the operating threshold is trustworthy. Middle scores (0.3-0.9) over-state probability (observed 11-35%) because the model was trained with balanced class weights. Treat the score as a ranking with a validated threshold, not as a percentage.

## 6. Where it is weaker
- P002 (transient, mild, AUROC 0.70) and P006 (episodic, 0.83): short episodes give the drift features little time; the rules catch both first.
- The model adds 0.37 false alerts per patient-day on top of the rules (spread over 6 patients); it halves median detection time in exchange.
- Windows above threshold outside events: P003 96, P004 87, P010 34, P001 27 (most are within the 30-s persistence filter or next to a real event).

## 7. Digital twin (held-out P008-P010, mean absolute error)
| Horizon | HR twin / no-change | RR twin / no-change | Calibrated 95% band coverage (HR, RR) |
|---|---|---|---|
| 5 min | 1.5-2.3 / 1.6-2.8 bpm | 0.7-1.1 / 0.8-1.5 /min | 94-97%, 97-99% |
| 15 min | 1.7-2.5 / 2.3-3.4 bpm | 0.7-1.2 / 0.9-1.6 /min | 95-97%, 98% |
| 30 min | 1.8-2.5 / 2.4-3.5 bpm | 0.7-1.2 / 1.0-1.6 /min | 96-97%, 98-99% |

During deteriorations the twin's 15-min HR error is less than half the physics-only model's (P009 5.6 vs 14.7 bpm). SpO2 on the stable patient is slightly worse than "no change" (0.10 vs 0.03 %), within sensor resolution. Equations are provisional pending clinical approval.

## 8. Limits
Labels come from the same simulator that generated the data; 9 events is a small sample (wide confidence intervals); BIDMC recordings are too short to test forecasts. Real-patient validation and clinical sign-off are required before any clinical use.
