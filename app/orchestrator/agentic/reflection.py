"""
🪞 Reflection Engine — Self-Critique & Retry Decision
=====================================================
File: app/orchestrator/agentic/reflection.py

After a plan executes, the agent reflects: "Did I actually achieve the
goal? Is the result trustworthy, or should I retry / escalate?"

Two reflection paths (same philosophy as the planner):
    1. LLM path — Gemini critiques the (goal, plan, results) triple and
       returns a structured verdict.
    2. Deterministic fallback — confidence/error heuristics over the tool
       results, so reflection ALWAYS yields a verdict.

A Reflection verdict drives the coordinator's loop:
    - status="accept"   → done, return the result.
    - status="retry"    → re-plan/re-execute (bounded by max_iterations).
    - status="escalate" → stop and flag for human review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Below this aggregate confidence, a result is not trustworthy on its own.
LOW_CONFIDENCE_THRESHOLD  = 0.45
ESCALATE_DECISIONS        = {"escalate", "manual_review", "legal_escalation"}


@dataclass
class Reflection:
    status:      str                 # "accept" | "retry" | "escalate"
    confidence:  float
    reason:      str
    source:      str  = "deterministic"
    suggestions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status":      self.status,
            "confidence":  round(self.confidence, 4),
            "reason":      self.reason,
            "source":      self.source,
            "suggestions": self.suggestions,
        }


_REFLECT_PROMPT = """You are the reflection module of an autonomous ERP agent.
Critically assess whether the GOAL was achieved by the executed PLAN + RESULTS.

GOAL: {goal}
RESULTS (tool outputs, JSON): {results}

Return ONLY a JSON object, no prose:
{{
  "status": "accept" | "retry" | "escalate",
  "confidence": <0.0-1.0>,
  "reason": "<short critique>",
  "suggestions": ["<what to change if retrying>"]
}}
Guidance:
- "accept": goal achieved, results coherent and trustworthy.
- "retry": fixable gap (missing/failed step, low confidence) worth one more attempt.
- "escalate": ambiguous, high-risk, or repeatedly failing → needs a human.
"""


class ReflectionEngine:
    async def reflect(
        self,
        goal: str,
        results: list,        # list[ToolResult-like dicts]
        iteration: int = 0,
        max_iterations: int = 2,
    ) -> Reflection:
        from orchestrator.agentic.llm_client import get_llm_client
        client = get_llm_client()

        # LLM attempt
        import json
        results_json = json.dumps(results, default=str, ensure_ascii=False)[:3000]
        prompt = _REFLECT_PROMPT.format(goal=goal, results=results_json)

        raw, used_llm = await client.complete_json(
            prompt=prompt,
            fallback=lambda: {},
            temperature=0.1,
        )

        if used_llm and raw.get("status") in {"accept", "retry", "escalate"}:
            status = raw["status"]
            # Never retry past the budget — downgrade to escalate.
            if status == "retry" and iteration + 1 >= max_iterations:
                status = "escalate"
            verdict = Reflection(
                status=status,
                confidence=_clamp(raw.get("confidence", 0.7)),
                reason=str(raw.get("reason", ""))[:300] or "LLM reflection",
                source="llm",
                suggestions=[str(s)[:160] for s in (raw.get("suggestions") or [])][:5],
            )
            logger.info("🪞 [Reflection/LLM] %s (conf=%.2f) — %s",
                        verdict.status, verdict.confidence, verdict.reason[:80])
            return verdict

        return self._deterministic(goal, results, iteration, max_iterations)

    # ── Deterministic fallback ────────────────────────────────────────────────

    def _deterministic(
        self, goal: str, results: list, iteration: int, max_iterations: int,
    ) -> Reflection:
        if not results:
            return Reflection(
                status=("escalate" if iteration + 1 >= max_iterations else "retry"),
                confidence=0.2,
                reason="No tool produced any result.",
            )

        failures = [r for r in results if not r.get("ok", True)]
        # Extract confidence + decision robustly from each tool output, which
        # may vary in shape (nested, string values, different key names, lists).
        confs:     list = []
        decisions: list = []
        for r in results:
            out = r.get("output", {})
            conf = _extract_confidence(out)
            if conf is not None:
                confs.append(conf)
            dec = _extract_decision(out)
            if dec:
                decisions.append(dec)

        agg_conf = (sum(confs) / len(confs)) if confs else (0.6 if not failures else 0.3)

        # 1) Any tool failed → retry once, then escalate.
        if failures:
            if iteration + 1 >= max_iterations:
                return Reflection("escalate", agg_conf,
                                  f"{len(failures)} tool(s) failed after retries.")
            return Reflection("retry", agg_conf,
                              f"{len(failures)} tool(s) failed — retrying.",
                              suggestions=[f"Fix failing tool: {failures[0].get('tool')}"])

        # 2) A decision explicitly asks for human review.
        if any(d in ESCALATE_DECISIONS for d in decisions):
            return Reflection("escalate", agg_conf,
                              "A step returned an escalate/manual_review decision.")

        # 3) Low aggregate confidence → retry, else escalate.
        if agg_conf < LOW_CONFIDENCE_THRESHOLD:
            if iteration + 1 >= max_iterations:
                return Reflection("escalate", agg_conf,
                                  "Confidence stayed low after retries.")
            return Reflection("retry", agg_conf,
                              "Aggregate confidence below threshold — retrying.")

        # 4) Healthy.
        return Reflection("accept", agg_conf,
                          "All tools succeeded with acceptable confidence.")


# ── Robust extractors (tolerant of varied tool-output shapes) ─────────────────

_CONFIDENCE_KEYS = ("confidence", "confidence_score", "conf", "score")
_DECISION_KEYS   = ("decision", "ai_decision", "ai_classification",
                    "classification", "review_level", "status")


def _extract_confidence(out) -> Optional[float]:
    """
    Pull a confidence in [0,1] from a tool output of unknown shape.
    Handles: dict with any of _CONFIDENCE_KEYS (possibly string/percent),
    nested 'output'/'result' dicts, and lists of such dicts.
    """
    if isinstance(out, list):
        vals = [_extract_confidence(o) for o in out]
        vals = [v for v in vals if v is not None]
        return (sum(vals) / len(vals)) if vals else None
    if not isinstance(out, dict):
        return None
    for key in _CONFIDENCE_KEYS:
        if key in out and out[key] is not None:
            v = _coerce_unit_float(out[key])
            if v is not None:
                return v
    # Recurse into common nesting wrappers.
    for nest in ("output", "result", "data"):
        if isinstance(out.get(nest), (dict, list)):
            v = _extract_confidence(out[nest])
            if v is not None:
                return v
    return None


def _extract_decision(out) -> Optional[str]:
    """Pull a decision/classification string from a tool output of unknown shape."""
    if isinstance(out, list):
        for o in out:
            d = _extract_decision(o)
            if d:
                return d
        return None
    if not isinstance(out, dict):
        return None
    for key in _DECISION_KEYS:
        val = out.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    for nest in ("output", "result", "data"):
        if isinstance(out.get(nest), (dict, list)):
            d = _extract_decision(out[nest])
            if d:
                return d
    return None


def _coerce_unit_float(v) -> Optional[float]:
    """Coerce a value to a float in [0,1]; '85%' → 0.85; 85 → 0.85; '0.9' → 0.9."""
    try:
        if isinstance(v, str):
            s = v.strip().rstrip("%")
            f = float(s)
            if v.strip().endswith("%") or f > 1.0:
                f = f / 100.0
            return max(0.0, min(1.0, f))
        f = float(v)
        if f > 1.0:                      # e.g. a 0-100 score
            f = f / 100.0
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return None


def _clamp(v, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return lo


_engine: Optional[ReflectionEngine] = None


def get_reflection_engine() -> ReflectionEngine:
    global _engine
    if _engine is None:
        _engine = ReflectionEngine()
    return _engine
