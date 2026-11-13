# 03 | Patient Recovery Assistant

Mobile-first white workspace, same Manrope and black body text. Patient accesses only authorized own records, not cohort selector or operator console. Keep disclaimer. No complex clinical score, raw FHIR, model uncertainty or clinician-only details in patient UI unless explicitly approved. No automatic diagnosis or treatment.

## Home
Header logo and “My recovery”, patient identity if authorized, simple care-plan status. One large section “Today's recovery plan” with completed/total approved tasks, progress bar and next scheduled task; no fabricated completion. If no active approved plan, say “Your care plan is not available yet” and direct to care team. Use white surfaces and large black text; do not add recovery hero media. Optional avatar from existing gender-matched asset, no inference if unknown. Monitoring summary: last data, device connection, plain guidance, existing watch assets only for actual simulated device context. No wearable claim for BIDMC.

## Daily tasks
List approved task title, scheduled time, instructions, completion status. Mark complete through server action, prevent double submit, reflect confirmed response; failed requests retain pending status with retry. Progress from confirmed task completions, not UI-only state. Do not assume fixed 7/15/30/90/180-day schedule; show approved duration and phase only. Do not suggest walking or activity if not approved. Past/future dates and timezone clearly labeled.

## Symptom check-in (optional PS03 hint)
Visible question “How are you feeling today?” with breathlessness, fever, dizziness, optional fatigue only if supported. Include explicit none option mutually exclusive with symptoms; severity/time/notes only if contract supports them. Patient enters, reviews, submits; show server receipt/time and clear failure. Backend integrates symptom evidence according to approved policy; UI does not add NEWS2 points. Do not label a symptom as diagnosis. If severe symptoms or safety guidance returned, show clear care-team/emergency instructions appropriate to backend policy; don't promise monitoring is emergency service. Don't invent notifications. History shows submitted responses, timestamps, receipt status.

## Medication
Display only approved current schedule as actionable reminders. Separate historical prescriptions and uncertain adherence from current confirmed regimen; no inferred current use. Dose, route, schedule only if actually present in approved plan. “Taken” records patient-reported completion, not verified ingestion. No autonomous medication changes, missed-dose instructions or generated dosage. If not available, direct to care team. Medication Expert suggestions are clinician review items, not patient orders.

## Progress and care team
Recovery phase, approved milestones, daily completion and trend summaries only when available. Avoid generic recovery percentage based on physiology. Display contact information from authorized care plan; no invented phone/email. Notifications use actual delivery status; Kannada/Hindi only if implemented with reviewed translations, optional. Maintain role separation and secure logout. Mobile bottom nav text labels Home, Tasks, Symptoms, Care plan; secondary history and settings accessible. 44px targets, 16px body, no overlapping fixed nav, keyboard accessible.

## Acceptance
Patient cannot read another patient, operator replay or clinician alert action. Unknown plan not replaced by demo defaults. Symptom and completion updates persist via backend, failures visible. No additional images/videos generated. Static avatar optional; use plain initials/ID when no match. Patient-facing copy simple and factual.
