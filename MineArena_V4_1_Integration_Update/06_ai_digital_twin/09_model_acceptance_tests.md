# Digital twin acceptance tests (pending execution)
Record PASS/FAIL/BLOCKED with code/model/data hash, run IDs, environment, actual outputs and limitations. No trained model assumed.

| ID | Pass criterion |
|---|---|
| AI01 | Identical causal runtime/offline manifest semantic hash, no biography or labels |
| AI02 | Exactly 264 indices and group counts, registry/normalizer version check |
| AI03 | Missing normalized zero mask0 vs valid zero mask1 |
| AI04 | No future observations, context, targets or label leakage in features |
| AI05 | Fixed 15s source frames despite adaptive gateway, correct replay offset |
| AI06 | Whole-run splits disjoint, normalization fit train only |
| AI07 | Approved four ODE equations, parameter units/bounds and applicability recorded |
| AI08 | Solver finite and physically plausible across held-out scenarios; failures explicit |
| AI09 | State estimate separate from observed values; artifact input handled without ground truth |
| AI10 | Forecast horizons and target offsets correct; missing horizon unavailable |
| AI11 | Actual MAE/RMSE against all feasible comparators, held-out run IDs |
| AI12 | Calibration validation only, test coverage/width and sample count reported |
| AI13 | Counterfactual branch isolation and evidence dedup |
| AI14 | OOD/missing model/timeout produce abstention or failure, no fake forecasts |
| AI15 | Experimental forecast cannot independently change clinical priority |
| AI16 | P0 urgent safety unaffected by model overload or HAPI outage |
| AI17 | Stale model result cannot overwrite newer state/alert floor |
| AI18 | Ten concurrent independent keys, P002-H and BIDMC isolation |
| AI19 | Checkpoint/weights reload reproduces output within declared tolerance |
| AI20 | BIDMC no synthetic temperature/clinical outcome claim |
| AI21 | Ground truth and artifact labels absent from runtime request/log/manifest |
| AI22 | Model disagreement with safety recorded, no downgrade |

Release: deterministic pipeline can be ready independent of model. Advanced inference blocked until equation approval, actual data, trained artifact and tests. No synthetic-only clinical validity claims.
