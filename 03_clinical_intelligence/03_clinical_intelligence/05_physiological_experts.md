# Four physiological expert specifications

**MineArena PS03 | Frozen Architecture V4.1 | Specification v1.0**

Engineering prototype only; clinical decision support, not diagnosis. Implementation, integration and clinical validation pending. All numeric timing and decision heuristics below are configurable engineering defaults, not clinical guidelines. Do not add architecture components or use SNN.

## 1. Shared execution
Experts 2–5 are deterministic evidence producers, run in parallel per completed 5/10/15s window, using the same context, score, quality and prior baseline snapshots. Every vital remains active. No disease diagnosis, medication dose changes or final priority decisions. No LLM needed. Immediate safety runs separately on every event. Inputs: identity, as-of time, window raw observation refs, 30s persistence, 60s and 5min trailing histories, baseline, score, context, applicable KB rules. Never inspect future samples, simulator metadata or hidden labels.

For each vital compute latest valid value, min/max/median, sample SD, valid/expected coverage, missing/suspect fractions, last measurement age, delta and robust z, trailing 60s robust slope (Theil–Sen of valid timestamps; unit per minute; require >=3 points spanning >=30s and >=80% coverage), 5min slope if sufficient history, contiguous abnormal duration (reset on gap >2 sample intervals, missing or normal), cumulative abnormal seconds over 30s, quality flags. Calculate duration from observed time intervals, cap contribution to nominal sample interval; do not count overlapping windows twice. No slope when insufficient history. Preserve original extremes. Score latest eligible value using 03.

## 2. Expert-specific logic
| Expert | Evidence | Contextual interpretation | Limits |
|---|---|---|---|
| HR | HR score, rising/falling trend, >=15 bpm candidate delta | Cardiac history; verified current beta blocker may blunt tachycardia; activity context | Historical prescription conditional only; normal HR does not exclude deterioration |
| RR | RR score, >=4/min candidate delta, persistence, zero/flatline quality | Respiratory history and oxygenation evidence | Zero requires verification; no respiratory diagnosis |
| SpO2 | Applicable scale, >=3 pp downward candidate, desaturation duration, probe pattern | Authorized scale and oxygen status; respiratory history | No inferred hypercapnia; isolated drop can be genuine |
| Temp | Temperature score, >=0.5 C candidate delta, rise/fall persistence | Infection history, thermal/HR changes | No inferred sepsis or postoperative status |

## 3. Concern and corroboration
Engineering classification per expert: unknown if no eligible current signal; none if score 0 and no candidate; mild if score 1 or candidate; moderate if score 2 or candidate persists >=20 eligible seconds in trailing 30s with >=80% coverage; high if component score 3 or moderate plus corroborating independent domain and applicable context. This expert concern is not final alert priority. Context-aware rule: persistent respiratory deviation plus documented respiratory illness history can generate Review via 07 even with zero score; same deviation without relevant context requires corroboration or more evidence (07). Verified beta blocker use may support interpretation of RR/SpO2 deterioration despite normal HR, not score reduction or fabricated evidence. Thermal and cardiac history are contextual interpretation, not automatic priority. Context unknown never vetoes safety.

Cross-signal support = number of other eligible domains with directionally compatible evidence / number of other evaluated eligible domains, null if none. Example falling SpO2 with rising RR and HR; rising temp with rising HR. Do not assume independence when derived from same observation; deduplicate by observation IDs/evidence group. Opposing changes are not proof of artifact. All hypotheses labeled possible/supported/contradicted/unknown, with limitations. No causal claim. For PINN-ODE pass relationship refs and applicability, not invented coefficients; equations/units/bounds remain joint team dependency.

## 4. ExpertEvidenceV1 logical fields
Identity, context/window/state versions, domain, evaluation status evaluated/insufficient_data/failed, current value, baseline deviation, trend slope, abnormal duration, clinical component score, concern ordinal none=0/mild=1/moderate=2/high=3 (unknown=null), cross support, baseline/signal availability, reliability ordinal 0=low,1=moderate,2=high (unknown=null), interpretation uncertainty 0=low,1=moderate,2=high (unknown=null), quality evidence, findings and hypotheses with rule/version, actual refs and evidence group, missing fields and limitations. Reliability separate from concern. High reliability requires valid fresh signal and adequate coverage; moderate for limited coverage/context; low for suspect/unverified quality. Unknown masks preserve absence, not zero. Encoder order/normalization stays in architecture contract. Output evidence not final priority. Failed expert cannot block independent safety.

## 5. Acceptance
P001 respiratory history + persistent falling SpO2/rising RR -> relevant historical fact and corroboration; P002 historical beta blocker -> conditional note only; P007 appendicitis encounter -> no surgery inference; missing Temp -> insufficient expert evidence; a normal HR cannot veto critical SpO2. Tests file 08.
