# Avoflare Dashboard V2: implementation report

Clinical decision support only. All patients and readings are simulated (Synthea context, simulated wearable) or BIDMC replay. Not clinical validation.

## Startup
```bash
cd avoflare
AVOFLARE_DEMO_LOGIN=1 python -m uvicorn server:app --port 8000
```
Clinician dashboard `http://localhost:8000`, patient app `http://localhost:8000/patient`. Generated credentials: `state/initial_credentials.txt`. Tests (server running): `python run_all_tests.py`.

## Capability inventory (audited against the running server)
| Capability | Available | Endpoint / source |
|---|---|---|
| Patient list, live vitals, priority, monitoring, alerts | Yes | WebSocket `/ws` event `overview` (every 1 s), `GET /api/overview` |
| Patient detail + 30 min series | Yes | `GET /api/patients/{pid}` |
| Profile (KB conditions, medication history, procedures) | Yes | `GET /api/patients/{pid}/profile` |
| Partial NEWS2 components, subtotal, max component | Yes | `score` in overview row (engine `clinical_score`) |
| Baseline value, status, freeze, delta, z | Yes | `vitals.*` in overview row, manifest `baseline_state` |
| Physiological expert evidence, rules, trust | Yes | `GET /api/patients/{pid}/intelligence` |
| Manifest, twin forecast 5/15/30 min, params, encoder fill | Yes | `GET /api/patients/{pid}/twin` |
| Counterfactual branches A–D | Yes | `POST /api/patients/{pid}/counterfactual` |
| Doctor Ava summary (deterministic formatter) | Yes (new) | `GET /api/patients/{pid}/summary` |
| Event timeline | Yes (new) | `GET /api/patients/{pid}/timeline` |
| Wearable presentation state (5 states) | Yes (new) | `device.state` in overview row |
| Care plan, Expert 6 review items, Expert 7 recovery | Yes | `GET /api/patients/{pid}/care`, `POST careplan`, `POST review/{item}` |
| Alert ack / receipt / resolve | Yes | `POST /api/alerts/{pid}/ack`, `/receipt`, `/resolve` |
| Notifications (criticality only) | Yes | `GET /api/notifications`, `POST /api/notifications/{id}/read`, `GET /api/notifications/team` |
| FHIR records | Yes | `GET /fhir/Observation` |
| Evaluation results, metrics, twin report | Yes | `GET /api/eval/summary` |
| Latency, outbox, FHIR validity, audit | Yes | `GET /api/eval/health` |
| Isolated replay (simulated cohort, BIDMC) | Yes | `POST /api/eval/replay` |
| Security test cases | Yes | `POST /api/eval/security-tests` |
| ClinicalReportV1 endpoint | No | Clinical reports route hidden |
| Replay pause / speed / reset controls | No | Explained in the console; runs complete in one pass |
| Three.js / WebGL | Not installed | CSS 3D spatial stage with SVG connectors; static under reduced motion |
| P0–P3 queue telemetry, Redis, worker heartbeat | No | Not shown |

## Files modified / added in V2
- `server.py`: summary formatter, timeline recorder, five wearable states, notifications endpoints, management reminder throttle, demo-only screenshot login route.
- `records.py`: notifications table + helpers, session index.
- `twin.py`: parameter rounding.
- `web/ui.css`: V2 tokens, opaque panels, blurred decorative background layer, spacing scale.
- `web/app.html`: rebuilt clinician app (Overview, Patients, Clinical alerts, Notifications, Evaluation, FHIR records, Settings; patient tabs Monitoring, Profile, Digital twin, Intelligence, Care plan, History).
- `test_platform.py`: Doctor Ava, timeline, wearable, notification checks.

## Reusable components (in `web/app.html`)
`Ava` (Doctor Ava avatar + speech + transcript), `chart` (observed/baseline/forecast/uncertainty SVG), `vitalPanel`, `devicePanel`, `newsPanel`, `alertBlock`, `identity`, `twinView` (spatial stage + node inspector), `hist` (timeline), `phoneScreen` (notification mockups), `tone`/`alarm` (urgent alarm).

## Backend-to-UI mapping (main fields)
`vitals[v].value|score|quality|baseline|baseline_status|delta|z|slope60|persistent|fresh` → vital panels, table, twin inspector · `score.components|observed_subtotal|maximum_available_subtotal|maximum_component_score|status` → NEWS2 panel · `priority|insufficient|rules|risk` → assessment and explanation · `alert.trigger|evidence|fact|deliveries|log|acknowledged|state` → alert evidence · `device.state|last_packet` → wearable panel · `summary.identity|assessment_version|assessment_time|sentences` → Doctor Ava · `forecast.status|reason|horizons|trajectory|source_t|equation_set` → twin charts · `events[].t|kind|text` → timeline.

## Doctor Ava
Server-side deterministic formatter over engine decision, score, baseline, context, alert lifecycle and approved care plan. It states only the recommendation the decision produced (immediate clinical assessment, clinical review, continue monitoring). Browser SpeechSynthesis, starts only on click; mouth moves on word-boundary events; stops on patient switch, page hide or sign-out; late responses for a previous patient are discarded by request id and identity check; transcript always available.

## Test results (executed)
- `run_all_tests.py`: see `results/scorecard.json` (latest: platform suite 56/56 including Doctor Ava, timeline, wearable and notification checks; two known failures: twin RR uncertainty coverage, SBP over-flagging).
- Security tests: 11/11 behave as expected; run time reduced from 49 s to 0.3 s by indexing.
- Screenshots: `results/screens/01_login.png` … `12_patient_app.png` (headless Edge against the live server).

## Known limitations
- Twin uncertainty bands under-cover RR and SpO2; equations provisional.
- SBP NEWS2 bands over-flag a young patient; no personal BP baseline.
- No WebGL twin (Three.js not available locally); CSS 3D stage used.
- Supplied wearable and login clips contain a dark strip; cropped in CSS, originals untouched.
- Replay has no pause/speed/reset; no ClinicalReportV1 endpoint; no P0–P3 queue telemetry.
- Speech voice depends on the operating system's installed voices.
