# Avoflare — PS03 post-discharge deterioration monitor (Architecture V4.1)

Clinical decision support prototype on **synthetic** data. Not a diagnosis, not clinical validation. Human review required.

## Run
```bash
pip install fastapi uvicorn numpy scipy pandas scikit-learn torch httpx
python sim.py              # 10 patients x 15 days, device 10 pps -> gateway 1 Hz   (data/)
python extra_vitals.py     # blood pressure + HRV every 5 min                         (data/*_bp_hrv.npz)
python train.py            # clinical engine over 15 days + risk model (LOPO)         (model/risk_model.pkl)
python twin.py             # PINN-ODE digital twin ensemble                           (model/twin.pt)
AVOFLARE_DEMO_LOGIN=1 python -m uvicorn server:app --port 8000
```
- Clinician dashboard: http://localhost:8000 · Patient app: http://localhost:8000/patient
- Accounts are generated on first start in `state/initial_credentials.txt` (doctors DR1–DR4, nurses NR1–NR3, management MG1, operator OPS1, patients PT-P001…PT-P010). `AVOFLARE_DEMO_LOGIN=1` adds labelled one-click demo buttons.
- Optional: `NTFY_URL` phone/smartwatch push, `HAPI_URL` real HAPI FHIR server, `SPEED`, `URGENT_TIMEOUT`, `REVIEW_TIMEOUT`.

Tests (server running): `python run_all_tests.py` → `results/scorecard.json`; full metrics `python evaluate_metrics.py`; report `python build_report.py` → `results/evaluation_report.html`.

## Live data flow
simulated wearable → HMAC-signed FHIR R4 Bundle → gateway (device auth, nonce/timestamp replay protection, FHIR validation, idempotent receipts) → durable store + outbox (cold path; forwards to HAPI when `HAPI_URL` set) → safety supervisor (every sample) → experts 1–5, partial NEWS2, personal baseline → 15 s manifest → digital twin forecast (experimental) → decision (Watch/Review/Urgent; risk model may raise to Review only) → alert lifecycle → alerting agent (patient's own doctor → nurse → substitute doctor → management, role-specific message + guidance, push) → WebSocket → dashboard.

## Files
| File | Layer |
|---|---|
| `sim.py`, `extra_vitals.py` | L1 virtual wearable (HR, RR, SpO2, Temp, BP, HRV) |
| `records.py` | L2 gateway security + FHIR, cold-path store/outbox, accounts, audit |
| `engine.py` | L2 quality/artifacts, L3 Expert 1, L4 Experts 2–5, partial NEWS2, baseline, L8 safety + decision, lifecycle |
| `twin.py` | L5 manifest, L6 264-slot encoder + PINN-ODE ensemble, L7 validity gate + counterfactuals |
| `care.py` | L9 Expert 6 medication review, Expert 7 recovery, care plans, symptoms |
| `train.py`, `evaluate_metrics.py` | risk model + PS03 evaluation |
| `server.py` | hot path, APIs, alerting agent, BIDMC/simulator isolated replay, security tests |
| `web/app.html`, `web/patient.html`, `web/ui.css` | L10 clinician dashboard, patient app, evaluation console (07_dashboard design system, Round 2 demo layout, all 8 supplied media assets) |
| `test_engine.py`, `test_extra_vitals.py`, `test_platform.py`, `run_all_tests.py` | tests |

## Digital twin (provisional)
dz/dt = −z/τ + [α_T·z_temp + α_A·activity]_HR + r_θ, z = (x − baseline)/S. Relaxation to the personal baseline, the V4.1 illustrative HR coupling, and a bounded neural residual penalised so the mechanistic part dominates. RK4, dt 15 s, horizons 5/15/30 min, 4-member ensemble. All coefficients are learned, none invented; equations need clinical/AI approval. Forecasts are experimental and never change priority. Abstains on missing baseline, < 3 vitals, out-of-distribution input, non-finite or out-of-bounds output.

## Deliberate tuning vs spec defaults (configurable in engine.py)
PERS-2 personal-range score 2 → Watch; reliable score needs latest value and trailing median (RR 60 s); ACT-1/2 exertion context; 6 h baseline reference. Evaluation convention: simulated clinician closure at eligibility, identical for the comparator.

## Known gaps
Twin uncertainty bands under-cover RR/SpO2; SBP NEWS2 bands over-flag a young patient (no personal BP baseline); patient-aware load balancing / P0–P3 lanes not separated; shared clinical KB rules live in code; adaptive 5/10/15 s windows fixed at 10 s; MATLAB generator replaced by `sim.py`.
