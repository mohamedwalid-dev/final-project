"""
✅ Finance Risk Handler v4.0 — Migration & Validation Script
=============================================================
File: app/agents/finance/validate_handler_v4.py

Run this after deploying risk_model_handler.py v4.0 to confirm:
  1. الـ handler بيـ load الموديل صح
  2. الـ feature count مطابق للـ training (41 features)
  3. مفيش shape mismatch في الـ prediction
  4. الـ rule-based fallback شغّال
  5. الـ GeminiQuotaGuard شغّال

Usage:
    cd app/
    python agents/finance/validate_handler_v4.py
    python agents/finance/validate_handler_v4.py --full   # مع اختبار الموديل الفعلي
"""

from __future__ import annotations

import argparse
import sys
import os

# ── Add project root to path ──────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

results = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = PASS if condition else FAIL
    msg    = f"  {status} {name}"
    if detail:
        msg += f" | {detail}"
    print(msg)
    results.append((name, condition))
    return condition


def warn(name: str, detail: str = "") -> None:
    print(f"  {WARN} {name}" + (f" | {detail}" if detail else ""))


# ══════════════════════════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════════════════════════

def test_imports() -> bool:
    print("\n── 1. Import Tests ──────────────────────────────────────────")
    ok = True

    try:
        from agents.finance.risk_model_handler import (
            get_finance_risk_handler,
            get_gemini_quota_guard,
            FinanceRiskModelHandler,
            GeminiQuotaGuard,
            RuleBasedPredictor,
        )
        check("Core imports", True)
    except ImportError as e:
        check("Core imports", False, str(e))
        return False

    # تأكد إن build_features مش موجودة بعد كده (اللي كانت سبب المشكلة)
    handler_cls = FinanceRiskModelHandler
    has_old_build = hasattr(handler_cls, "build_features")
    check(
        "build_features() REMOVED (was root cause)",
        not has_old_build,
        "Still present — delete it" if has_old_build else "Correctly removed",
    )
    ok = ok and not has_old_build

    return ok


def test_quota_guard() -> bool:
    print("\n── 2. GeminiQuotaGuard Tests ────────────────────────────────")
    from agents.finance.risk_model_handler import get_gemini_quota_guard

    guard = get_gemini_quota_guard()
    check("Guard available initially", guard.is_available())

    guard.mark_exhausted()
    check("Guard blocks after mark_exhausted()", not guard.is_available())
    check("Guard status shows exhausted", guard.get_status()["available"] is False)

    # Reset for further tests
    guard._exhausted_at = None
    check("Guard recovers after reset", guard.is_available())
    return True


def test_rule_fallback() -> bool:
    print("\n── 3. Rule-Based Fallback Tests ─────────────────────────────")
    from agents.finance.risk_model_handler import RuleBasedPredictor

    predictor = RuleBasedPredictor()

    # Test 1: High risk
    result = predictor.predict({
        "overdue_days": 120, "amount": 500000,
        "credit_score": 350, "industry": "construction",
        "payment_history_count": 10, "payment_history_paid": 2,
        "payment_history_late": 8,
    })
    check("High risk case → reject/manual_review",
          result["decision"] in ("reject", "manual_review", "legal_escalation"),
          f"decision={result['decision']} score={result['risk_score']:.3f}")

    # Test 2: Low risk
    result = predictor.predict({
        "overdue_days": 0, "amount": 5000,
        "credit_score": 820, "industry": "government",
        "payment_history_count": 20, "payment_history_paid": 19,
        "payment_history_late": 1,
    })
    check("Low risk case → approve",
          result["decision"] == "approve",
          f"decision={result['decision']} score={result['risk_score']:.3f}")

    # Test 3: Missing fields (graceful handling)
    result = predictor.predict({})
    check("Empty dict → no crash",
          isinstance(result, dict) and "risk_score" in result,
          f"decision={result.get('decision')}")

    return True


def test_handler_singleton() -> bool:
    print("\n── 4. Handler Singleton Tests ───────────────────────────────")
    from agents.finance.risk_model_handler import get_finance_risk_handler

    h1 = get_finance_risk_handler()
    h2 = get_finance_risk_handler()
    check("Singleton pattern works", h1 is h2)

    info = h1.get_info()
    check("get_info() returns dict", isinstance(info, dict))
    check("model_path in info", "model_path" in info)
    check("gemini_quota in info", "gemini_quota" in info)
    check("architecture in info", "architecture" in info)

    return True


def test_handler_predict_rule_mode() -> bool:
    """Test predict() when ML model is NOT loaded (rule fallback)."""
    print("\n── 5. Handler predict() — Rule Fallback Mode ────────────────")
    from agents.finance.risk_model_handler import FinanceRiskModelHandler

    # Create fresh instance with no model loaded
    handler = FinanceRiskModelHandler.__new__(FinanceRiskModelHandler)
    handler._predictor    = None
    handler._metadata     = {}
    handler._loaded       = False
    handler._version      = "rules-v4.0"
    handler._trained_at   = "unknown"
    handler._feature_count = 41

    test_data = {
        "overdue_days": 8,
        "amount": 26890,
        "credit_score": 680,
        "industry": "retail",
        "payment_history_count": 10,
        "payment_history_paid": 7,
        "payment_history_late": 3,
        "customer_age_months": 13,
        "invoice_count_90d": 1,
        "avg_payment_delay_days": 0,
        "customer_id": "cust-test-001",
        "invoice_id":  "inv-test-001",
    }

    result = handler.predict(test_data, request_id="val-test-001")

    check("predict() returns dict",    isinstance(result, dict))
    check("risk_score present",        "risk_score" in result)
    check("decision present",          "decision" in result)
    check("latency_ms present",        "latency_ms" in result)
    check("model_version present",     "model_version" in result)
    check("source is rule-based",      "rules" in result.get("source", ""))
    check("NO shape mismatch error",   "_error" not in result or "shape" not in result.get("_error", ""),
          "shape mismatch would appear in _error field")

    print(f"    risk_score: {result.get('risk_score')}")
    print(f"    decision:   {result.get('decision')}")
    print(f"    source:     {result.get('source')}")
    print(f"    latency:    {result.get('latency_ms')}ms")

    return True


def test_handler_predict_ml_mode(full: bool = False) -> bool:
    """Test predict() when ML model IS loaded."""
    print("\n── 6. Handler predict() — ML Mode ──────────────────────────")

    if not full:
        warn("Skipped (run with --full to test ML model)",
             "requires trained model at models/finance/payment_risk_v8.pkl")
        return True

    from agents.finance.risk_model_handler import get_finance_risk_handler

    handler = get_finance_risk_handler()

    if not handler.is_loaded():
        warn("ML model not found",
             "run: python training/finance_train.py first")
        return True

    check("ML model loaded", True, f"version={handler._version} features={handler._feature_count}")

    # Critical check: feature_count must be 41
    check(
        "Feature count is 41 (not 11)",
        handler._feature_count == 41,
        f"got {handler._feature_count} — if 11, model was trained with old handler",
    )

    test_data = {
        "overdue_days": 8,
        "amount": 26890,
        "credit_score": 680,
        "industry": "retail",
        "payment_history_count": 10,
        "payment_history_paid": 7,
        "payment_history_late": 3,
        "customer_age_months": 13,
        "invoice_count_90d": 1,
        "avg_payment_delay_days": 0,
        "customer_id": "cust-test-ml-001",
        "invoice_id":  "inv-test-ml-001",
        "invoice_month": 5,
        "days_to_due": 30,
    }

    try:
        result = handler.predict(test_data, request_id="val-ml-001")

        check("ML predict() no crash",          True)
        check("NO shape mismatch",              "_error" not in result or
              "shape" not in result.get("_error", ""))
        check("risk_score in [0, 1]",           0.0 <= result.get("risk_score", -1) <= 1.0)
        check("source is ml (not emergency)",   "emergency" not in result.get("source", ""))

        print(f"    risk_score: {result.get('risk_score')}")
        print(f"    decision:   {result.get('decision')}")
        print(f"    source:     {result.get('source')}")
        print(f"    latency:    {result.get('latency_ms')}ms")

    except Exception as e:
        check("ML predict() no crash", False, str(e))
        return False

    return True


def test_decision_mapping() -> bool:
    print("\n── 7. Decision Mapping Tests ────────────────────────────────")
    from agents.finance.risk_model_handler import FinanceRiskModelHandler

    cases = [
        # (raw_decision, review_level, risk_score, expected_keywords)
        ("approve",  None,        0.10, ["approve"]),
        ("review",   "monitor",   0.30, ["soft_follow_up"]),
        ("review",   "escalate",  0.45, ["hard_follow_up"]),
        ("reject",   None,        0.75, ["legal_escalation"]),
        ("reject",   None,        0.55, ["hard_follow_up"]),
    ]

    for raw, level, score, expected in cases:
        mapped = FinanceRiskModelHandler._map_decision(raw, level, score)
        ok     = any(kw in mapped for kw in expected)
        check(
            f"map({raw}, level={level}, score={score:.2f})",
            ok,
            f"→ {mapped} (expected one of {expected})",
        )

    return True


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Validate Finance Risk Handler v4.0")
    parser.add_argument("--full", action="store_true",
                        help="Run ML model tests (requires trained model)")
    args = parser.parse_args()

    print("=" * 65)
    print("  Finance Risk Handler v4.0 — Validation Suite")
    print("=" * 65)

    all_passed = True
    all_passed &= test_imports()
    all_passed &= test_quota_guard()
    all_passed &= test_rule_fallback()
    all_passed &= test_handler_singleton()
    all_passed &= test_handler_predict_rule_mode()
    all_passed &= test_handler_predict_ml_mode(full=args.full)
    all_passed &= test_decision_mapping()

    print("\n" + "=" * 65)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"  Results: {passed} passed | {failed} failed")

    if all_passed and failed == 0:
        print("  ✅ ALL CHECKS PASSED — safe to deploy")
    else:
        print("  ❌ SOME CHECKS FAILED — review before deploying")
        for name, ok in results:
            if not ok:
                print(f"     ❌ {name}")
    print("=" * 65)

    sys.exit(0 if all_passed and failed == 0 else 1)


if __name__ == "__main__":
    main()