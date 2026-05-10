"""
⚙️ HR Decision Thresholds — Centralized Constants
===================================================
File: app/config/hr_thresholds.py

🎯 Single source of truth للـ thresholds.
   كل الـ components تيجي تاخد منه بدل hardcoding.

Tier System:
    Tier 1 — ML confidence >= TIER1_APPROVE_THRESHOLD  → auto approve (no LLM)
    Tier 2 — TIER3_REJECT_THRESHOLD <= conf < TIER1    → Gemini LLM reviews
    Tier 3 — ML confidence <  TIER3_REJECT_THRESHOLD   → auto reject (no LLM)

Priority (highest → lowest):
    1. model_metadata["thresholds"]  ← optimal thresholds from training pipeline
    2. hr_thresholds.py constants    ← static fallback defaults
    3. hardcoded inline values       ← NEVER use this — always import from here
"""

# ── Tier 1: High-confidence auto-approve ──────────────────────────────────────
TIER1_APPROVE_THRESHOLD: float = 0.72
"""
فوق الـ threshold ده → ML يوافق تلقائياً بدون LLM.
مطابق لـ THRESHOLD_APPROVE في training/hr_train.py.
"""

# ── Tier 2: Gray zone — LLM review required ──────────────────────────────────
# الـ range هو: TIER3_REJECT_THRESHOLD  ≤  conf  <  TIER1_APPROVE_THRESHOLD
# مفيش threshold خاص هنا، الـ range بيتحسب تلقائياً.

# ── Tier 3: Low-confidence auto-reject ───────────────────────────────────────
TIER3_REJECT_THRESHOLD: float = 0.42
"""
تحت الـ threshold ده → ML يرفض تلقائياً بدون LLM.
مطابق لـ THRESHOLD_ESCALATE في training/hr_train.py
(فوق ده escalate، تحته reject).
"""

# ── Validation Layer Thresholds ───────────────────────────────────────────────
VALIDATION_MIN_CONFIDENCE_FOR_APPROVE: float = 0.60
"""
الـ DecisionValidationLayer يرفض أي approve بثقة أقل من ده
حتى لو الـ LLM أعطى موافقة — safety net إضافي.
"""

# ── LLM Config ────────────────────────────────────────────────────────────────
LLM_TIMEOUT_SECONDS: int = 25
"""
لو Gemini اتأخر أكتر من كده → fallback للـ ML decision.
"""

# ── Risk Classification ───────────────────────────────────────────────────────
RISK_LOW_THRESHOLD: float    = 0.80
RISK_MEDIUM_THRESHOLD: float = 0.50
"""
فوق RISK_LOW    → risk = "low"
بين الاتنين     → risk = "medium"
تحت RISK_MEDIUM → risk = "high"
"""

# ── Quality Gate (used in training pipeline) ──────────────────────────────────
QUALITY_GATE_MIN_AUC: float         = 0.65
QUALITY_GATE_MIN_EDGE_CASE_PASS: float = 0.70
"""
لو الـ model مش وصل للـ thresholds دي → training pipeline يعمل warning.
"""

# ── Helper: load dynamic thresholds from model metadata ──────────────────────

def get_thresholds_from_metadata(metadata: dict) -> dict:
    """
    يجيب الـ thresholds من model metadata لو موجودة.
    بيرجع static defaults لو الـ metadata فاضي أو ناقص.

    Args:
        metadata: dict من LeaveModelHandler._metadata

    Returns:
        {
            "approve":   float,
            "escalate":  float,
            "reject":    float,   # دايماً 0.0
            "tier1":     float,   # alias لـ approve
            "tier3":     float,   # alias لـ escalate
        }
    """
    meta_thresholds = metadata.get("thresholds", {})

    t_approve  = float(meta_thresholds.get("approve",  TIER1_APPROVE_THRESHOLD))
    t_escalate = float(meta_thresholds.get("escalate", TIER3_REJECT_THRESHOLD))

    return {
        "approve":   t_approve,
        "escalate":  t_escalate,
        "reject":    0.0,
        "tier1":     t_approve,
        "tier3":     t_escalate,
    }


def classify_risk(confidence: float) -> str:
    """
    يحوّل confidence score لـ risk label.
    نسخة centralized بدل ما كل agent يعمل copy.
    """
    if confidence >= RISK_LOW_THRESHOLD:
        return "low"
    elif confidence >= RISK_MEDIUM_THRESHOLD:
        return "medium"
    return "high"


def apply_standard_threshold(confidence: float) -> str:
    """
    Standard 3-tier decision gate.
    يستخدم الـ constants المعرّفة هنا — مش hardcoded.
    """
    if confidence >= TIER1_APPROVE_THRESHOLD:
        return "approve"
    elif confidence >= TIER3_REJECT_THRESHOLD:
        return "escalate"
    return "reject"