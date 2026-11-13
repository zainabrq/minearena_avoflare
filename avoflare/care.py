"""Layer 9: Expert 6 (medication & intervention review items) and Expert 7 (patient recovery), care plans,
patient task completion and symptom check-in. Nothing here prescribes or changes doses: Expert 6 produces review items
that a clinician approves or dismisses; care plans exist only when a clinician creates them (audited)."""
import time, uuid
import numpy as np
from records import kv_get, kv_set, audit

SYMPTOMS = ("breathlessness", "fever", "dizziness", "fatigue")


def plan(pid):
    return kv_get(f"plan:{pid}")


def save_plan(pid, actor, phase, duration_days, tasks, meds, contact):
    p = {"pid": pid, "phase": phase, "duration_days": int(duration_days), "approved_by": actor, "approved_at": time.time(),
         "contact": contact, "version": (plan(pid) or {}).get("version", 0) + 1,
         "tasks": [{"id": uuid.uuid4().hex[:8], "title": t["title"], "time": t.get("time", ""), "instructions": t.get("instructions", "")}
                   for t in tasks if t.get("title")],
         "medications": [{"label": m["label"], "schedule": m.get("schedule", ""), "status": "approved current"} for m in meds if m.get("label")]}
    kv_set(f"plan:{pid}", p); audit(actor, "care_plan_approved", pid, "ok", f"v{p['version']}")
    return p


def completions(pid, day):
    return kv_get(f"done:{pid}:{day}", {})


def complete_task(pid, day, task_id, actor):
    p = plan(pid)
    if not p or task_id not in {t["id"] for t in p["tasks"]}: return None
    d = completions(pid, day)
    if task_id not in d:
        d[task_id] = time.time(); kv_set(f"done:{pid}:{day}", d); audit(actor, "task_complete", pid, "ok", task_id)
    return d


def symptoms(pid):
    return kv_get(f"sym:{pid}", [])


def add_symptoms(pid, actor, chosen, severity, note, source_t):
    if "none" in chosen and len(chosen) > 1: raise ValueError("'none' cannot be combined with symptoms")
    bad = [c for c in chosen if c not in SYMPTOMS + ("none",)]
    if bad or not chosen: raise ValueError("choose at least one listed option")
    rec = {"id": uuid.uuid4().hex[:8], "at": time.time(), "source_t": source_t, "symptoms": chosen, "severity": severity, "note": note[:300]}
    h = symptoms(pid) + [rec]; kv_set(f"sym:{pid}", h[-50:]); audit(actor, "symptom_checkin", pid, "ok", ",".join(chosen))
    serious = any(c in chosen for c in ("breathlessness", "dizziness")) or severity == "severe"
    rec["guidance"] = ("Your care team has been sent this report. If you are struggling to breathe, have chest pain or feel faint, "
                       "call emergency services now. This app is not an emergency service.") if serious else \
                      "Thank you. Your care team can see this report."
    rec["notify_care_team"] = chosen != ["none"]
    return rec


def expert6(ctx, kb, decision, bp):
    """Medication & intervention review items from documented history + current evidence. Pending clinician review."""
    meds = [m["label"].lower() for m in kb.get("medication_history", [])]
    ex = (decision or {}).get("experts") or {}
    items = []
    def add(i, text, why): items.append({"id": i, "text": text, "evidence": why, "status": kv_get(f"rev:{ctx['patient_id']}:{i}", "pending clinician review")})
    if ctx.get("beta_blocker_history"):
        add("MED-BB", "Confirm whether a beta blocker is currently taken; it may blunt a rising heart rate.",
            "beta blocker in prescription history; current use unknown")
    if any(k in m for m in meds for k in ("lisinopril", "amlodipine", "losartan", "hydrochlorothiazide")) and bp and (bp.get("sbp_score") or 0) >= 1:
        add("MED-BP", "Review antihypertensive use against the current low systolic reading.", f"SBP {bp.get('sbp')} mmHg with antihypertensive history")
    if any(k in m for m in meds for k in ("albuterol", "fluticasone", "salmeterol", "inhal")) and (ex.get("rr", {}).get("score") or 0) >= 2:
        add("MED-INH", "Check inhaler availability and technique with the patient.", "inhaler history with raised respiratory rate")
    if (ex.get("temp", {}).get("score") or 0) >= 1:
        add("INT-FEVER", "Consider infection screen and review of wound or source of fever.", f"temperature {ex['temp']['value']} C")
    if (decision or {}).get("priority", 0) >= 3:
        add("INT-ESC", "Arrange urgent in-person assessment; consider ambulance.", "current priority Urgent")
    return {"expert": "Expert 6 Medication & intervention", "items": items,
            "limits": "Review items only. No prescriptions, doses or autonomous treatment."}


def expert7(pid, d, t_now, plan_, done_today, sym):
    """Recovery summary from device activity, overnight heart rate and approved plan; no physiology-based recovery %."""
    day = int(t_now // 86400)
    rows = []
    for k in range(max(0, day - 6), day + 1):
        s, e = k * 86400, min((k + 1) * 86400, t_now)
        if e <= s: continue
        act_min = int(d["activity"][s:e].sum() / 60)
        night = d["hr"][s + 2 * 3600: min(e, s + 5 * 3600)]
        rows.append({"day": k + 1, "active_minutes": act_min,
                     "overnight_hr": None if not np.isfinite(night).any() else round(float(np.nanmedian(night)), 1)})
    hr = [r["overnight_hr"] for r in rows if r["overnight_hr"]]
    trend = None if len(hr) < 3 else round(hr[-1] - float(np.median(hr[:-1])), 1)
    return {"expert": "Expert 7 Patient recovery", "day_since_discharge": day + 1, "daily": rows,
            "overnight_hr_change_vs_prior_days": trend,
            "plan": None if not plan_ else {"phase": plan_["phase"], "duration_days": plan_["duration_days"],
                                            "tasks_done_today": len(done_today), "tasks_total": len(plan_["tasks"])},
            "recent_symptoms": sym[-3:],
            "limits": "Activity is device-reported movement, not an approved exercise record. No recovery percentage is computed."}
