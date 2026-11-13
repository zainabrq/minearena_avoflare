# MineArena PS03 implementation status

**Workspace snapshot: 13 November 2026**  
Prototype status: engineering demo; not a medical device, diagnosis service, or clinically validated workflow.

## Completed in this workspace

- Preserved the existing V4.1 specifications, patient files, Avoflare assets, clinical engine, and training pipeline.
- Added an always-visible critical alarm panel to the dashboard. An Urgent scripted replay alert opens the panel; an operator can run a routing drill, mark the doctor/nurse/substitute doctor/management office available, acknowledge locally, enable a browser buzzer, and request browser notifications.
- Added role-specific handoff text. The demo advances an unacknowledged alert every 12 seconds and skips recipients marked unavailable.
- The existing `avoflare/engine.py` contains the deterministic four-vital scoring, expert rules, temporal policy, alert lifecycle, and fixed comparator. `avoflare/train.py` contains a leave-one-patient-out training/evaluation pipeline.
- Trained a separate experimental risk classifier from the repository simulator and wrote its artifact, model card, and report under `avoflare/artifacts/synthetic_simulator_run_v1/`. It was smoke-loaded and produced a finite prediction for a 36-feature input.

## Not connected or not available

- The user-referenced file `D:\PS03_wearable_10_patients_15_days_10pps.zip` is not present in this workspace, and the `D:` drive is not mounted. The workspace has ten Synthea profile/FHIR records and simulator configuration. It also has derived `win_P001.npz`–`win_P010.npz` feature caches: 129,600 windows per patient, 36 features per window, covering 15 days at 10-second windows. The cache contains engine/comparator outputs but no independent `y` ground-truth label.
- The synthetic training labels were regenerated from the supplied simulator. The first derived feature window for each of the ten patients matched recomputation from the regenerated source arrays; a complete raw-to-feature hash/recompute audit was not completed.
- A new-seed holdout was run for P003 over a 12,300-second event window with 1,800 seconds of warm-up. On 1,230 windows and one generated event, the model scored AUROC 0.739 and AUPRC 0.715; its frozen 0.98 threshold fired zero windows. Rules-only and rules-plus-model both detected the one event and produced two false clinical episodes. See [P003_event_window_report.json](avoflare/artifacts/synthetic_simulator_run_v1/unseen_seed_2027/P003_event_window_report.json). This is one synthetic event, not a meaningful clinical validation sample.
- The model artifact has 36 inputs, while the current engine emits 44. The holdout passed the first 36 features and excluded eight appended slow-drift features. The artifact is not directly runtime-compatible. A full 44-feature retraining pass was started but stopped before producing caches or a model.
- The user-referenced ZIP and its independent labels are still missing, so the model above was **not trained on the requested archive**. A separate simulator-generated `labels.json` was used for an engineering-only model. Its ten patient-held-out folds produced synthetic window AUROC 0.8825 and AUPRC 0.3473 over 1,296,000 windows. At the selected threshold, rules-plus-ML detected 9/9 generated events but produced 76.273 false clinical episodes per patient-day; it matched the rules-only result and showed no incremental benefit. Threshold metrics reused the pooled LOPO predictions for selection, so they are not an independent test. This artifact is not suitable for patient care or production alerting.
- Model files: [risk_model.pkl](avoflare/artifacts/synthetic_simulator_run_v1/model/risk_model.pkl), [model_card.json](avoflare/artifacts/synthetic_simulator_run_v1/model_card.json), [report.json](avoflare/artifacts/synthetic_simulator_run_v1/results/report.json), and [MODEL_README.md](avoflare/artifacts/synthetic_simulator_run_v1/MODEL_README.md). The separate derived-window inventory remains in [avoflare/results/dataset_readiness.json](avoflare/results/dataset_readiness.json); its priority counts are rule outputs, not ground truth.
- `avoflare/server.py` and `avoflare/web/index.html` contain a separate replay website/backend prototype with role escalation. It reads the same unavailable dataset at startup, uses in-memory state, exposes unauthenticated action routes, and has placeholder staff entries. It is not production staff messaging or a verified care-team directory.
- The React dashboard remains marked simulation mode with backend disconnected. Its alarm panel does not deliver SMS, phone, email, push-to-device, or server-side staff messages. Real staff identity, availability, acknowledgement, routing persistence, and escalation timers need an authenticated backend and configured recipients.
- Clinical rules and the partial NEWS2-style score remain engineering prototype policy. The local rules specify four scored vitals only; the full RCP NEWS2 system includes six parameters. Do not use complete-NEWS2 escalation thresholds against the partial subtotal. Scale 2 requires documented qualified-clinician authorization.
- The dashboard fixture alerts are scripted demo events, not assessments generated from the ten patient records. No real-time wearable stream, HAPI FHIR service, validated digital twin, or verified care-team contact directory is connected.

## Safety and clinical sources

The supplied clinical specification and the existing engine implement local configurable engineering rules. The authoritative NEWS2 component bands and Scale 2 direction are published in the [Royal College of Physicians NEWS2 chart (December 2022)](https://www.rcp.ac.uk/media/eczf5mvm/news2-chart-3_news-observation-chart_2022_0_0.pdf). This application is not a substitute for local clinical governance, clinician assessment, or emergency procedures.

## To enable the requested cohort model work

Place the supplied ZIP inside the workspace or provide its extracted directory, including the independent event labels (`labels.json`). If any patient feature cache is absent or incompatible, include the source observation arrays needed to regenerate it. Then audit the schema, source provenance, labels, run/patient splits, and existing `engine.py` assumptions before running the training pipeline. Keep ground-truth labels isolated from runtime inference and report synthetic evaluation separately from clinical validation.

## Alarm behavior in this prototype

The dashboard's “Start routing drill” button creates a clearly marked test event with no patient data. Browser sound and notifications require explicit operator activation. A local acknowledgement stops the buzzer but does not resolve a clinical episode. Timers run only while the dashboard page is open; they do not provide dependable on-call coverage.
