# 06 | Dashboard acceptance test matrix

These are expected tests, not executed results. Use actual backend integration tests with isolated session IDs and controlled fixtures. Clinical rule test expectations come from 03_clinical_intelligence; metric truth comes from 08_evaluation. Record test ID, build/contract versions, input/session, observed output, evidence screenshot/log, pass/fail/blocker. Never mark pass for unimplemented feature. Recommended Vitest + Testing Library and Playwright if project supports them; otherwise equivalent.

| ID | Test | Expected result |
|---|---|---|
| UI-01 | Desktop login, mobile login | White split layout, supplied logo and hero, readable form, no media blocks sign-in |
| UI-02 | Invalid login/logout | Backend error visible; logout clears state and subscriptions |
| UI-03 | Unauthorized route/API | No patient or operator data exposed; server denies unauthorized access |
| UI-04 | Overview with ten actual loaded patients | Counts match authorized data, all four vitals and priorities visible, filters correct |
| UI-05 | Empty cohort | Clear empty state, no fake patient rows or counts |
| UI-06 | Select P001 then P003 while old requests pending | No cross-patient chart, context, alert or video leakage |
| UI-07 | P002 and P002-H concurrent | Isolated profile, baseline, scale, session and alert state |
| UI-08 | BIDMC session | No Synthea history or invented temperature, replay identity visible |
| UI-09 | Four valid observations | Units, timestamps, component score and backend subtotal agree |
| UI-10 | Example HR108 RR26 SpO2 92 temp38.1 Scale1 | Components 1,3,2,1 and subtotal 7/12 if backend policy same; no UI recompute |
| UI-11 | Missing or suspect value | Unavailable/suspect label, gap in chart, incomplete scoring, no fake normal |
| UI-12 | Scale2 authorized overlay vs original | Correct authorized scale/target context, no COPD-only inference |
| UI-13 | Calibration/freeze/resume | Actual eligible baseline state and reason, no fabricated progress |
| UI-14 | Old clinical history | Historical readings not baseline; current medication use unknown if unconfirmed |
| UI-15 | Immediate safety event before routine window | Alert visible immediately without waiting forecast, HAPI or video |
| UI-16 | Watch/Review/Urgent examples | Exact backend priority, rule and evidence; color plus text |
| UI-17 | Incomplete assessment | Separate insufficient state; not represented as healthy Watch |
| UI-18 | Alert detail | Actual reading/unit/time/ref, rule/version and patient fact/ref or unavailable explanation |
| UI-19 | Acknowledge | Server confirmed acknowledgment; episode remains unresolved |
| UI-20 | Urgent then normal observation | Highest unresolved Urgent persists, current assessment can differ |
| UI-21 | Resolve unauthorized/failed request | No optimistic closure; permission/error shown |
| UI-22 | Confirmed simulated removal | Removed video/still, technical status and actual evidence; no diagnosis |
| UI-23 | Suspected artifact only | Suspected wording; no assertion of confirmed band removal |
| UI-24 | Network disconnect | UI disconnected/stale, attachment unknown; no automatic removed clip |
| UI-25 | Confirmed reattachment | Attached media only after confirmation; urgent episode preserved |
| UI-26 | Concurrent true deterioration and probe fault | Clinical and technical alerts coexist; reliable independent evidence visible |
| UI-27 | Video missing, slow or autoplay blocked | Static fallback or textual state, monitoring unaffected |
| UI-28 | Reduced motion | Static posters, no animated 3D or scrolling fades |
| UI-29 | WebGL unavailable | Textual twin/2D node fallback; all evidence and charts still available |
| UI-30 | Manifest inspection | Textual state/context ref/version; no duplicated history, no hidden truth |
| UI-31 | Observed vs estimate vs forecast | Distinct labels/styles/timestamps; uncertainty shown, no invented values |
| UI-32 | Experimental/abstained/failed forecast | Explicit status, no fabricated prediction or priority change |
| UI-33 | Counterfactual branch | Separate isolated result; original patient state unchanged, no treatment claim |
| UI-34 | Expert missing output | Not evaluated, no fabricated confidence or finding |
| UI-35 | Patient without approved care plan | Clear unavailable state; no invented tasks/doses |
| UI-36 | Patient task/symptom submission | Confirmed server persistence; failure shown; no client score alteration |
| UI-37 | Patient cross-account access | Server rejection, no patient data leakage |
| UI-38 | Replay stable/slow/artifact | Actual source data, controls and session lifecycle work |
| UI-39 | BIDMC accelerated replay | Correct source-time axis, distinct wall clock, no temperature |
| UI-40 | Evaluation not run | Pending/not run, no fabricated metrics |
| UI-41 | Evaluation actual result | Compare both systems, show exposure, misses, lead/delay, false and technical episodes |
| UI-42 | Zero metric denominator | Not applicable, not zero; negative lead shown as late |
| UI-43 | HAPI persistence failed | Accepted != stored; error shown, safety unaffected |
| UI-44 | FHIR resource inspection | Actual retrieved resource, coding, unit or absent reason and validation evidence |
| UI-45 | Duplicate/out-of-order event | Deduplicated, no stale assessment overwrite |
| UI-46 | Reconnect and resync | Correct session snapshot restored, no invented samples or alert loss |
| UI-47 | Ten concurrent streams | Actual measured latency and no cross-session state, media remains isolated |
| UI-48 | Responsive 1440/1280/1024/768/390 widths | No page overflow; charts/table scroll contained, urgent visible before media |
| UI-49 | Keyboard and screen reader | All controls reachable, focus visible, drawer restores focus, labels and status announced |
| UI-50 | 200% zoom/contrast | Content readable, no clipped values; WCAG AA target verified |
| UI-51 | Visual audit | Pure white, black body, forest headings, Manrope, no prohibited patterns from 01 |
| UI-52 | Asset audit | Exactly supplied three video roles/five image roles; actual extensions resolved; no missing assets silently |
| UI-53 | Production build | Clean build, no console errors on primary flows; no secrets or hardcoded clinical data |
| UI-54 | Disclaimer | Visible on login and all workspaces; no diagnosis or validated efficacy claims |
| UI-55 | Demo vs live separation | Fixture label unmistakable, fixtures excluded from actual evaluation/report |

## Visual review checklist
Review actual screenshots at desktop 1440x900 and mobile 390px, not only code. Compare spacing, typography, alignment, readable numeric units, neutral surfaces, media crop, white background and accessible priority. No decorative icon grids, gradients, glass, grain, emoji, Lucide icons, scroll fades or cursor effects. Inspect source copy for em dashes and buzzwords. Verify browser focus and keyboard operation manually. Urgent content remains visible without scrolling past large media.

## Release gate
P0 mandatory flows must pass or be listed as blockers with actual evidence. Optional P1/P2 unavailable states acceptable if disclosed. Run stable, slow deterioration, probe removal and BIDMC demos using real ingestion. Verify at least five qualifying Synthea profiles with relevant conditions and medications actually influencing monitoring, not just displayed. Do not infer home discharge, active meds or clinical validation. Record actual comparative metrics only. No claim of implementation completion from these specifications.
