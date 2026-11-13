# Avoflare | Dashboard implementation specification

Version 1.0. MineArena PS03. Frozen system architecture V4.1. A React and TypeScript frontend is available in simulation mode. See [Run the dashboard](RUN_DASHBOARD.md). Build the real React application in this directory alongside the existing assets. Do not replace or delete assets. No new system modules, clinical algorithms, agents, SNN or architecture redesign.

## Read in this order
1. `../00_requirements/` original PS03 (sections 3.1–3.7, 5, 8).
2. `../01_architecture/` authoritative V4.1 architecture and current shared contracts.
3. `../02_patient_data/` existing Patient KB and FHIR records; `../03_clinical_intelligence/` all eight specifications.
4. `../08_evaluation/` scenario and metric definitions; `../04_simulation/` actual streaming interface.
5. `01_ui_design_system.md` and `design_tokens.json` are mandatory visual constraints; then 02–08 in order.

## Product and deliverables
Avoflare is a clinical decision-support prototype, not a diagnosis system. Three workspaces: clinician (desktop-first), patient (mobile-first), evaluation (operator-only). All three share white spatial visual language. Implement real backend integration, not a mock dashboard. Existing assets: three videos, five images. No further visual assets required. Use procedural 3D only for computational twin; the wristband uses supplied videos, not an additional 3D asset.

Required outputs: runnable React/TypeScript source, production build, integration mapping to actual API/contracts, tests, asset audit, startup instructions, and demo run evidence. Suggested directories under `07_dashboard`: `src/app`, `src/routes`, `src/components`, `src/features`, `src/api`, `src/state`, `src/styles`, `src/tests`, `assets/images`, `assets/videos`. Keep specification files. Use existing repository package manager and configuration if present.

## Priorities
P0: working login/authorized session, monitoring queue, individual patient, four vital trends, patient facts, partial NEWS2, explained tiered alerts, artifact handling, simulator/BIDMC replay, actual report and FHIR inspection. P1: wearable state-driven media, digital twin, manifest/forecast, expert/trust panels, clinical reports, approved medication/recovery. P2: optional 3D branch refinement, patient symptoms and multilingual notifications where backend supports them. P0 must not depend on P1/P2.

## Authority and blockers
Backend contracts and clinical policies are authoritative. API paths in these documents are logical operations, not verified routes. Inspect actual OpenAPI and current contracts before coding adapter; record mapping and missing endpoints. Never recreate clinical rules in frontend. Exact PINN-ODE parameters/model validation remain upstream dependencies. Do not invent results, current medications, discharge facts, or physical attachment. Show explicit unavailable or experimental state. Only source-derived values may be called live. Demo fixture mode must be clearly labelled, separate, and excluded from actual evaluation. No simulated ground truth in runtime clinical UI. All code must be written during the hackathon per PS03; confirm organizer policy on coding assistants if needed.
