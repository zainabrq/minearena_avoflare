# Avoflare | V4.1 integration addendum
Status: implementation specification, not implemented or clinically validated. System architecture version remains V4.1; backend revision V1.1.

## Authority and decisions
Original PS03 sections 3.1–3.7 are mandatory. Backend Architecture Design.pdf (40 pages) is the frozen system architecture. This addendum resolves backend implementation conflicts with Backend Architecture Design _ final (2).pdf (53 pages, HEALTHGUARD) and the FHIR teammate's subsequent status handoff. The AI training handoff is a supporting design reference, not an executed dataset or model. Clinical specifications in 03, UI in 07, and evaluation in 08 remain applicable except explicitly revised here. No new architecture layers, agents, SNN or model replacement. The HEALTHGUARD name and eight-layer backend view are not a new product/system architecture.

| Issue | Binding implementation resolution |
|---|---|
| Transport | NGINX TLS/WSS, device JWT, per-device HMAC-SHA256, nonce/sequence/idempotency, patient-scoped auth. |
| Ingestion | POST /api/v1/observations is proposed, accepts native R4 Observation; optional source adapter converts raw JSON before common gateway. Both MATLAB and BIDMC use it. No duplicate clinical pipeline. |
| Scoring | Four component scores, observed subtotal 0–12 with coverage; maximum eligible component 0–3 supplementary only. No full NEWS2 thresholds. Authorized Scale2 and causal rolling baselines. |
| Clinical priority | Preserve SAFE/CLIN rules and independent floor; age is contextual, not automatic escalation. Processing P0–P3 separate. |
| Priority streams | P0 immediate safety; P1 contextual review; P2 routine; P3 offline batch. All accepted events feed ordered clinical timeline and persistence irrespective of queue. Interactive replay has isolated P0–P2 equivalents and no live recipients. |
| Reliability | PostgreSQL transactional event/outbox, Redis Streams at-least-once, idempotent consumers, protected urgent capacity, HAPI circuit breaker, reconciliation. Infrastructure controller never changes clinical severity. |
| Identity | Existing P001–P010 and original Synthea FHIR IDs. Source namespace + patient/subject + variant + session; authorize device separately. P002-H synthetic overlay isolated; BIDMC independent. |
| Time | Separate physiological source time, effective time, signed request transmission time, receipt and publication clocks. ±30s proposed transmission freshness only. |
| Clinical facts | Patient Context service is sole direct Patient KB reader; downstream receive versioned references/snapshots. Shared Clinical KB separate. |
| Model | Textual manifest, 264 features, fixed 15s source frames, hybrid PINN-ODE; asynchronous outside safety, stale results discarded. Experimental forecasts cannot independently change priority. |
| UI | Existing white spatial design, 5 images and 3 videos unchanged. Add delivery lifecycle, queue health, security evidence. |

## Routing and durability invariants
Independent safety runs on each authorized validated observation, including potentially critical suspect readings. It does not wait for queues, context refresh, windows, model, HAPI or full report. P0 delivery uses protected capacity. Every accepted event is committed with durable handoff records; if no durable path available, do not return accepted. Best-effort safety may still be attempted with explicit degraded status. All observation processing preserves original evidence. Ordered per-session timeline and conditional version writes prevent stale results lowering a safety floor. No ground truth, scenario onset or future data in runtime or model inputs. Clinical and technical alerts separate, acknowledgement not resolution.

## Completion and limitations
FHIR teammate states endpoint, auth, HAPI setup and persistence are not verified; inspect actual code if available and implement missing pieces once. AI handoff describes proposed dataset sizes, feature groups and training method, not actual data sufficiency or trained weights. Equations, parameter constraints and exact context/temporal feature semantics require approval; see 06. Record actual results and blockers, not mock metrics. Clinical decision support, not diagnosis. All code written during hackathon; verify organizer coding-assistant policy.
