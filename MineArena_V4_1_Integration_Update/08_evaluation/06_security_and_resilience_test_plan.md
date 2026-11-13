# Security, queue isolation and resilience evaluation
All cases isolated synthetic environment; approved test credentials only. No unrestricted external attack capability. Record run/commit/config, trace, expected and observed outcome, timestamps, PASS/FAIL/BLOCKED, clinical/FHIR side effects, P0 performance and recovery evidence.

| Test | Expected result |
|---|---|
| Expired/forged JWT | 401; no state mutation |
| Modified body/invalid HMAC | rejected, integrity audit |
| Reused nonce / stale transmission | rejected; historical source time with fresh transmission accepted |
| Same event/hash fresh retry | previous receipt, one effect |
| Same ID different body | conflict and audit |
| Wrong patient/variant/session | denied before routing |
| Forged clinical priority | schema rejects or ignores explicitly; never trusted |
| Malformed FHIR / unsupported code | validation failure; no clinical state mutation |
| Rate burst | bounded throttling, protected P0 |
| Unauthorized WS subscription or receipt | denied, no patient disclosure |
| Worker crash before ack | reclaim and idempotent effect |
| Redis outage | durable outbox or honest 503; recovery without duplicates |
| HAPI outage | safety continues, pending backlog, reconcile GET on recovery |
| Model unavailable/overloaded | independent safety and observed decision continue |
| Browser disconnected | pending delivery, reconnect/resync, urgent remains unresolved |
| Cross-session late model result | rejected, no state overwrite |

Measure baseline ten-stream load and induced P2/P3 saturation with same hardware/cadence; record queue depth/age, p50/p95/p99 and n for ingress→handoff, sample→browser, stage timings, dropped/rejected counts and recovery. P0 <500ms p95 is proposed target only. Do not count engineering attacks as clinical deterioration events. Capture redacted log/actual API evidence and HAPI read results. Separate security certification and clinical validation from prototype test success.
