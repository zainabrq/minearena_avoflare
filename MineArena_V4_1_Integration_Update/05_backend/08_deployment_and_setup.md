# 08 | Deployment and setup

This is a setup specification; exact commands, ports and versions depend on teammate implementation. Claude must produce actual runnable README, lockfiles, Compose configuration and environment template after inspection. Do not invent working endpoint/port or claim containers launched.

## Suggested repository layout
Keep existing code if present. Within 05_backend, logical modules for app entrypoint, shared contract imports, gateway/source adapter, FHIR client, persistence/outbox, scoped state, clinical orchestration, AI adapter, alerts/care, REST/WS transport, security/audit and tests. These are code organization, not architecture layers. Keep one canonical clinical implementation from 03 and one model implementation from 06. Do not create new competing backend.

## Services
NGINX, FastAPI, HAPI FHIR R4, PostgreSQL operational state, Redis Streams, frontend and isolated workers according to the V1.1 plan. Keep HAPI and internal storage on private network. Pin actual compatible versions; use existing dependency lock. Health/readiness distinguishes service alive, ingestion available, HAPI pending/degraded and model unavailable. No requirement to make optional AI readiness block core monitoring.

## Configuration inventory
Document actual names/defaults for API bind/port, HAPI base URL and credentials, state DB, queue, producer auth keys, user auth configuration, allowed origins, TLS, patient registry/KB and shared knowledge paths, event freshness/nonce policy, sample/window/lateness parameters, persistence retries, queue bounds, model artifact/version/deadline, evaluation output, log retention. Provide `.env.example` placeholders only. Never commit secrets. Resolve relative paths consistently from project root. Include local synthetic mode and explicit limitations if TLS/encryption not configured locally.

## Startup order
1. Verify final V4.1 contract package and source adapters; install locked dependencies.
2. Launch actual HAPI/state/queue services; verify capability statement and health.
3. Idempotently import authorized synthetic patient resources and registry mapping; validate refs.
4. Start backend, confirm readiness, auth, ingestion and safety endpoints.
5. Run one MATLAB stream through actual FHIR and retrieve stored data; then BIDMC replay.
6. Start frontend, validate live snapshot/stream and alert lifecycle.
7. Run clinical fixtures, integration tests and actual evaluation scenarios.
8. Integrate 06 model only with compatible artifacts; rerun safety, model failure and isolation tests.

## Operational recovery
Document start/stop, clean synthetic reset (explicit destructive command only), backup/restore, failed outbox inspection/retry, HAPI reconciliation, model rollback, session restart and log collection. Preserve audit and unresolved alerts when restarting. No reset of original patient data without authorization. Include troubleshooting for port conflict, HAPI readiness, wrong patient mapping, invalid FHIR, websocket auth, queue backlog and unavailable model.

## Deliverable evidence
Actual repository commit, dependency versions, tested setup commands, actual API mapping/OpenAPI, test outputs, sample persisted resource IDs, performance report and known limitations. Keep all generated artifacts reproducible; all code written during hackathon per PS. Verify organizer policy on coding assistants if not established. No claims of production readiness.


## V4.1 integration revision (Backend V1.1)
Selected implementation plan: NGINX public edge (TLS/WSS upgrade), FastAPI, Redis Streams with AOF and noeviction, PostgreSQL app DB/outbox, dedicated P0 safety, P1 clinical, P2 twin/routine, P3 background and FHIR workers, HAPI JPA R4 with separate DB/role, React frontend. One Postgres server with separate DBs acceptable. Docker Compose on one host; not true fault isolation. Use actual pinned versions after compatibility check. Add readiness for each dependency, protected internal ports, bounded Redis retention based on acknowledgements, XAUTOCLAIM pending recovery, circuit breaker, safe restart. Configure JWT issuer/audience, keys, HMAC per-device secrets, ±30s skew, queue limits, worker concurrency and latency target, HAPI URL from deployed configuration; no secrets committed. Test actual HAPI capability/create/read; record configuration and actual startup commands. NGINX TLS certificate configuration and local-demo limitations must be disclosed. No fake URLs or claims of running services.
