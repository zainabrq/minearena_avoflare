# 05 | Frontend integration and runtime state

## Stack and architecture
React + TypeScript, Vite if no existing build system, CSS modules or existing Tailwind setup, Recharts or Plotly for charts, Three.js/React Three Fiber for the optional twin scene. Use current installed versions and lockfile; do not add a second design library. React Router or existing router. Reuse existing auth, API client and shared schema types. Prefer generated types from actual OpenAPI or an explicit mapping layer. No new backend services or architecture components.

Suggested structure: `src/app` shell/auth/router, `src/features/{overview,monitoring,profile,alerts,twin,intelligence,care,patient,evaluation,fhir}`, `src/components` shared accessible primitives, `src/api` transport/adapters, `src/state` identity-scoped stores, `src/styles` tokens, `src/tests` integration. Keep 07 specifications and assets; build outputs under dist. Add a local README with exact setup commands, environment names, backend dependencies, route mapping and test commands. No secrets in browser environment variables.

## Contract mapping
Inspect current architecture and backend before coding. The operations below are semantic, not invented URL paths. Create an integration table with actual method/path or stream topic, request/response contract and implementation status; mark absent operations honestly. Do not deploy mock endpoint names. No direct client calls to patient KB; use authorized backend context API. No raw clinical algorithm implementation in browser.

| Logical operation | Authoritative data / contracts | Consumer |
|---|---|---|
| Authenticate, session, logout | Existing backend auth and role | all workspaces |
| List authorized patient/session summaries | identity, ClinicalDecisionV1, ClinicalScoreV1, latest observation, active episode | overview |
| Fetch patient context and profile | ClinicalContextV1, authorized PatientKBRecordV1 facts | profile, monitoring |
| Snapshot + observation history | ObservationEventV1, ObservationWindowV1, BaselineStateV1 | monitoring |
| Live observation/decision updates | observation, SafetyAssessmentV1, ClinicalScoreV1, ClinicalDecisionV1, quality, episode refs | monitoring, alerts |
| Expert findings | ExpertEvidenceV1, context/rule refs | intelligence |
| Digital twin snapshot/history | PhysiologicalManifestV1, PatientTwinStateV1, ODEParameterStateV1, NeuralForecastV1 | twin |
| Trust and branch results | TrustAssessmentV1, backend counterfactual result | intelligence |
| Alert list, acknowledge, resolve | backend episode and authorized action/audit | alerts |
| Report, care plan, symptom/task updates | ClinicalReportV1, CarePlanV1, actual approved update schemas | care, patient |
| Replay/session controls | simulator API and run identity | evaluation |
| Comparative results | 08_evaluation actual aggregate and event tables | evaluation |
| HAPI inspection | authorized observation retrieval and validation evidence | FHIR |

## Identity and state boundaries
State key = source namespace + patient/subject ID + variant ID + session ID. Never use display name or bare patient ID as sole state key. Keep context version, state/checkpoint version, sequence/event identity and source timestamp. Authorize requests and subscriptions server-side; role-based route guards are convenience, not security. On patient/session change cancel pending fetches, detach old subscription, clear chart/alert/media buffers, show loading until correct snapshot. Ignore late async results whose key/version does not match. P002-H must never overwrite P002; BIDMC recording identity separate. Logout clears caches and media state. Avoid persistent browser storage for patient data; no patient details in URLs beyond approved opaque identifiers, logs or analytics.

## Live transport
Use existing authenticated WebSocket transport for live events; use REST snapshot/history and actions if supported. Gateway still owns adaptive 5/10/15-second windows; immediate safety events must reach UI independently, and model frames remain fixed 15-second source time. Frontend does not resample into clinical decisions or delay safety for render batching. Subscribe only to authorized scopes. Establish snapshot + sequence checkpoint, then merge events; deduplicate by event ID and reject stale state versions. If transport lacks sequence, coordinate snapshot refresh/resync contract rather than guessing. Allow out-of-order observations in history according to timestamp policy; never let older decision overwrite newer one. Reconnect with bounded exponential backoff and jitter, reauthorize and resync; show reconnecting/stale and last known value/time. Polling fallback only if existing API supports it, not equivalent to immediate safety guarantee. Clean subscriptions on unmount. Never fake live status during reconnect.

## Time, quality and presentation state
Preserve source physiological time vs receive/wall clock vs assessment time. Accelerated replay uses source time on charts; wall time for freshness and latency per actual session policy. Label timezone and units. Backend determines stale/quality/monitoring state; if browser transport fails, mark UI disconnected independently. Display missing as unavailable and break plotted line; retain last valid value with date and separate label. No zero substitution, trend smoothing, invented baselines, fake temperature for BIDMC. Technical episode and clinical episode independent. No normal packet clears urgent. Acknowledge/resolve only server confirmation, permission and audit.

Wearable visual state is presentation-only: confirmed simulated attachment/removal from authorized simulator presentation events or backend state explicitly confirmed. Do not feed hidden scenario labels or ground truth into clinical decisions. If only clinical inference exists, show suspected removal text and neutral static visual; do not label confirmed physical state. Network lost = attachment unknown, not removed. After reconnect do not assume attached without evidence. See 07.

## Performance and resilience
Use bounded chart buffers and history pagination; retain raw server history independently. Render coalesced routine observations via animation frame/short batching if needed; safety/alert events never wait. Lazy-load evaluation and 3D; video failure and WebGL failure isolated by error boundary. Pause offscreen media, avoid rendering 3D on overview. Use cancellation/timeout for requests; retries only idempotent operations or server idempotency keys. Action in flight disables repeat submission; show error and retry. Backend-driven metrics only. Measure client receipt-to-display and end-to-end with valid clocks; target dashboard publication-to-visible <1s as provisional engineering target, record p50/p95/p99 with ten streams. Do not claim target passed without measurement.

## Required UI states and security
Each data view supports loading, empty, ready, stale, partial, failed, unauthorized, and reconnecting. Keep previous values visibly stale only for same identity. No skeleton pretending to be data, no indefinite spinner without explanation. Escape server text, render JSON as text, never unsafe HTML. No tokens in URLs, source code or console. Use secure auth mechanism provided by backend, CSRF protection if cookie-based, TLS in deployment, actual role checks and no secrets exposed. Provide accessible keyboard focus, reduced motion, captions for state-changing media and nonvisual equivalents. Build smoke test against actual backend before demo.


## V4.1 integration revision (Backend V1.1)
Map authorized delivery receipt and acknowledgement separately; browser receipt does not imply clinician review. Add scoped queue/worker/health/security APIs, replay-only alert recipients and outbox/persistence status. Use actual OpenAPI from 05; no direct HAPI/Redis calls. UI must handle stale or degraded delivery independently of clinical severity.
