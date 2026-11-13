# Priority processing and Clinical Traffic Integrity Controller
Within existing V4.1 gateway/backend. No new clinical policy or layer.

| Lane | Purpose | Worker behavior |
|---|---|---|
| P0 | Mandatory safety/verification delivery | Protected consumer and resources; urgent action immediately; durable delivery state before acknowledgement. |
| P1 | Priority contextual review | Clinical evidence processing on ordered per-session timeline. |
| P2 | Routine monitoring, baseline, manifest and model | Same timeline; expensive model jobs isolated and deadline-limited. |
| P3 | Offline batch evaluation/analytics | Best effort, bounded concurrency, never live clinical recipients. |

Use Redis streams proposed `avoflare:urgent`, `avoflare:review`, `avoflare:routine`, `avoflare:background`; separate consumer groups, independent FHIR persistence queue. Final names configuration, not deployed. Interactive replay uses isolated equivalent lane/session with demo-only notification. All accepted events fan out to one ordered clinical timeline + persistence; P0 work additional, not exclusive. Dedup per event/purpose. Safety evaluation occurs before queue assignment; queue labels do not determine medical severity. No automatic age escalation; maximum component score supplementary. P0 reserved worker/concurrency, separate model worker; avoid shared blocking connection pool. Initial 50/25/20/5 capacity split from teammate is an optional load-test hypothesis, not clinical rule or guaranteed CPU partition.

## Durable processing
Atomic PostgreSQL event/outbox acceptance; publish retry with stable IDs; Redis at-least-once, XREADGROUP, XACK only after durable result, XAUTOCLAIM abandoned pending entries; idempotent state/notification/FHIR effects. AOF, noeviction, bounded retention only after required consumers complete. Outbox recover after Redis outage; no 202 without reliable handoff. Immediate best-effort safety for validated data may continue if durable store down but report degraded and failure honestly. FHIR retry independent; never wait for HAPI to notify. Protect unresolved alerts on restart.

## Controller
Monitor queue depth, oldest age, pending, worker heartbeat, throughput, errors, CPU/memory, Redis capacity, delivery and HAPI backlog. If overloaded reserve P0, throttle P2/P3/background/model, apply bounded producer backpressure, defer nonurgent jobs, allow controlled idle capacity borrowing without starving routine timeline. Never drop accepted event silently, reduce clinical severity, skip safety or turn missing into normal. If P0 unavailable, surface explicit degraded/failed delivery, retain pending and notify operator; alternate channel only if actually implemented. Record policy version, reason and recovery. Test ten streams, model load, Redis failure, HAPI outage, worker crash, slow client.

## Timing
P0 proposed p95 <500ms NGINX ingress to WS handoff; P1/P2 <750/1000ms first eligible result after work ready, separate collection/window/15s frame/model. Report p50/p95/p99, count, hardware, load, wall timestamps; measure browser receipt separately from acknowledgement. These are targets, not achieved values. Preserve clinical latency and evaluation protocol.
