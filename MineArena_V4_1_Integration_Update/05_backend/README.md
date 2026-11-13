# Avoflare backend handoff

**Specification V1.1 | Frozen system architecture V4.1 | MineArena PS03**

This package defines implementation requirements, not executed backend code. Authoritative system design: `01_architecture/Backend Architecture Design.pdf` (the supplied 40-page V4.1 document). The original PS03 is the mandatory acceptance authority. Clinical policy lives in `03_clinical_intelligence/`; UI behavior in `07_dashboard/`; evaluation in `08_evaluation/`. Do not add architecture layers, experts, SNNs, or duplicate clinical logic.

## Read and implement in order
1. `01_backend_architecture.md`: responsibilities, execution paths and failure isolation.
2. `02_gateway_and_ingestion.md`: authentication, validation, source adapters, windows.
3. `03_fhir_integration.md`: R4 resource mapping, persistence and reconciliation.
4. `04_api_and_websocket_contracts.md`: logical operations and frontend transport.
5. `05_patient_state_management.md`: identity, state, ordering, versions and lifecycle.
6. `06_security_and_audit.md`: authorization, source integrity, privacy and audit.
7. `07_backend_acceptance_tests.md`: test plan and evidence requirements.
8. `08_deployment_and_setup.md`: development, startup and release gates.
9. `09_integration_handoff.md`: unresolved teammate inputs and ownership.

## Claude instructions
Inspect existing FHIR/backend and simulator code before choosing actual endpoint paths, shared schema definitions, storage, or dependencies. Preserve the teammate's functioning implementation; adapt rather than duplicate. Read updated Pydantic contracts from 01_architecture; these specifications name logical fields and operations, not authoritative wire field names. The V4.1 PDF explicitly says earlier contracts require updates. Maintain a mapping from logical interfaces to actual contracts. If a contract is absent, coordinate an explicit versioned implementation proposal; mark it provisional. Never treat the architecture examples as verified patient facts.

Deliver P0 mandatory working functionality first. Model-dependent functions may be unavailable while 06_ai_digital_twin is unfinished; immediate safety and observed clinical assessments must continue. Use actual FHIR resources, real server persistence, verified patient context and executed tests, not fabricated results. Keep all simulator ground truth offline and isolated from clinical processing. Clinical decision support only, not diagnosis or autonomous treatment. All numerical timing targets are engineering defaults requiring measurement.


## V4.1 integration revision (Backend V1.1)
Backend V1.1 supersedes V1. Read architecture addendum and contract amendments first, then 01–11. FHIR teammate's handoff explicitly says endpoint, HAPI, mapping, security and tests are unverified; implement once if absent, preserve verified code if found. Use Avoflare branding; HEALTHGUARD is supporting engineering design only. Adopt NGINX, PostgreSQL, Redis Streams, HAPI R4, HTTPX, PyJWT/HMAC. Exact endpoint below proposed, not deployed. 10 defines queues and controller, 11 source adapter. Do not wait for trained model to demonstrate mandatory monitoring.
