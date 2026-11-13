"""Boundary tests for BP / shock index / HRV scores. Run: python test_extra_vitals.py"""
from extra_vitals import sbp_score, shock_score, hrv_score, assess

CASES = [  # (name, got, expected)
    ("SBP-90", sbp_score(90), 3), ("SBP-91", sbp_score(91), 2), ("SBP-100", sbp_score(100), 2),
    ("SBP-101", sbp_score(101), 1), ("SBP-110", sbp_score(110), 1), ("SBP-111", sbp_score(111), 0),
    ("SBP-219", sbp_score(219), 0), ("SBP-220", sbp_score(220), 3), ("SBP-110.5-rounds-up", sbp_score(110.5), 0),
    ("SBP-missing", sbp_score(None), None),
    ("SI-0.89", shock_score(89, 100), 0), ("SI-0.90", shock_score(90, 100), 1), ("SI-1.0", shock_score(100, 100), 2),
    ("SI-no-bp", shock_score(100, None), None),
    ("HRV-drop-29%", hrv_score(35.5, 50), 0), ("HRV-drop-30%", hrv_score(35, 50), 1), ("HRV-drop-50%", hrv_score(25, 50), 2),
    ("HRV-no-baseline-9", hrv_score(9), 2), ("HRV-no-baseline-14", hrv_score(14), 1), ("HRV-no-baseline-20", hrv_score(20), 0),
    ("HRV-missing", hrv_score(None, 50), None),
    ("ASSESS-shock", assess(88, 55, 12, 120, {"sbp": 125, "rmssd": 30})["shock_score"], 2),
    ("ASSESS-delta", assess(88, 55, 12, 120, {"sbp": 125, "rmssd": 30})["sbp_delta"], -37),
    ("FLAG-sbp90-always", assess(90, 60, 30, 80, {"sbp": 95, "rmssd": 30})["sbp_flag"], True),
    ("FLAG-sbp99-near-own-baseline", assess(99, 60, 30, 80, {"sbp": 107, "rmssd": 30})["sbp_flag"], False),
    ("FLAG-sbp99-drop-from-130", assess(99, 60, 30, 80, {"sbp": 130, "rmssd": 30})["sbp_flag"], True),
    ("ASSESS-monitoring-only", assess(88, 55, 12, 120, None)["status"], "monitoring_only"),
]

if __name__ == "__main__":
    fail = [(n, g, e) for n, g, e in CASES if g != e]
    print(f"PASS {len(CASES) - len(fail)}  FAIL {len(fail)}", fail or "")
    raise SystemExit(1 if fail else 0)
