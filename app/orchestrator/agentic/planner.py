"""
🗺️ Goal Planner — Self-Planning
================================
File: app/orchestrator/agentic/planner.py

Turns a high-level GOAL into an ordered list of PlanStep objects, each
naming a tool from the registry and the args to call it with.

Two planning paths:
    1. LLM path  — Gemini decomposes the goal against the live tool catalog
                   and returns a JSON plan. Validated against the registry.
    2. Deterministic fallback — a rule-based decomposer keyed on the goal's
       `kind`, so planning ALWAYS produces a runnable plan even with no API
       key / exhausted quota / unparseable LLM output.

The planner never executes anything — it only produces a plan. Execution
is the coordinator's job.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    tool:        str
    args:        dict
    rationale:   str = ""
    step_id:     str = field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    # Optional: map a previous step's output field into this step's args
    # at execution time, e.g. {"risk_score": "$step-ab12.risk_score"}.
    depends_on:  list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_id":    self.step_id,
            "tool":       self.tool,
            "args":       self.args,
            "rationale":  self.rationale,
            "depends_on": self.depends_on,
        }


@dataclass
class Plan:
    goal:    str
    steps:   list
    source:  str           # "llm" | "deterministic"
    notes:   str = ""

    def to_dict(self) -> dict:
        return {
            "goal":   self.goal,
            "source": self.source,
            "notes":  self.notes,
            "steps":  [s.to_dict() for s in self.steps],
        }


_PLANNING_PROMPT = """You are the planning module of an autonomous ERP agent.
Decompose the GOAL into an ordered list of tool calls. Use ONLY the tools below.

AVAILABLE TOOLS:
{tools}

GOAL: {goal}
CONTEXT (input data you may pass into tool args): {context}

Return ONLY a JSON object of this exact shape, no prose:
{{
  "steps": [
    {{"tool": "<tool_name>", "args": {{...}}, "rationale": "<why>"}}
  ],
  "notes": "<one-line summary of the plan>"
}}
Rules:
- Each "tool" MUST be one of the available tool names exactly.
- Put concrete values from CONTEXT into "args".
- Keep the plan minimal: only the steps needed to achieve the GOAL.
- Order matters: earlier steps run first.
"""


class GoalPlanner:
    def __init__(self):
        pass

    async def plan(self, goal: str, context: dict, kind: str = "") -> Plan:
        """
        Build a Plan for `goal`. Tries the LLM first, then falls back to a
        deterministic decomposition. Always returns a validated Plan.
        """
        from orchestrator.agentic.tools import get_tool_registry
        from orchestrator.agentic.llm_client import get_llm_client

        registry = get_tool_registry()
        client   = get_llm_client()

        # LLM attempt
        prompt = _PLANNING_PROMPT.format(
            tools=registry.specs_text(),
            goal=goal,
            context=_safe_context(context),
        )
        raw, used_llm = await client.complete_json(
            prompt=prompt,
            fallback=lambda: {"steps": [], "notes": "fallback"},
            temperature=0.1,
        )

        if used_llm and isinstance(raw.get("steps"), list) and raw["steps"]:
            steps = self._validate_steps(raw["steps"], registry)
            if steps:
                logger.info("🗺️ [Planner] LLM plan: %d step(s) for goal '%s'",
                            len(steps), goal[:60])
                return Plan(goal=goal, steps=steps, source="llm",
                            notes=str(raw.get("notes", ""))[:200])
            logger.info("🗺️ [Planner] LLM plan had no valid steps — deterministic fallback")

        return self._deterministic(goal, context, kind, registry)

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_steps(raw_steps: list, registry) -> list:
        valid = []
        for s in raw_steps:
            if not isinstance(s, dict):
                continue
            tool = s.get("tool")
            if not tool or registry.get(tool) is None:
                logger.debug("🗺️ [Planner] dropping unknown tool '%s'", tool)
                continue
            valid.append(PlanStep(
                tool=tool,
                args=s.get("args", {}) if isinstance(s.get("args"), dict) else {},
                rationale=str(s.get("rationale", ""))[:200],
            ))
        return valid

    # ── Deterministic fallback decomposer ─────────────────────────────────────

    def _deterministic(self, goal: str, context: dict, kind: str, registry) -> Plan:
        """
        Rule-based decomposition keyed on `kind`. When no kind is supplied it
        is inferred via the SHARED taxonomy (orchestrator.agentic.kinds) so the
        agentic layer and the trigger engine never disagree on what a goal is.
        Guarantees a runnable plan with no LLM.
        """
        from orchestrator.agentic.kinds import infer_kind

        k = (kind or infer_kind(goal, context)).lower()
        steps: list = []

        if k == "leave_review":
            steps = [
                PlanStep("hr.employee_lookup",
                         {"employee_id": context.get("employee_id")},
                         "Fetch employee record for context"),
                PlanStep("hr.leave_decision", dict(context),
                         "Run HR AI agent on the leave request"),
            ]
        elif k == "salary_review":
            steps = [PlanStep("hr.salary_decision", dict(context),
                              "Run salary decision engine")]
        elif k == "incentive_review":
            # No dedicated incentive tool yet — hand off to the HR agent inbox,
            # which routes 'incentive' intents correctly via the message bus.
            steps = [PlanStep("coord.agent_handoff",
                              {"recipient": "hr_agent", "intent": "incentive",
                               "payload": dict(context)},
                              "Route incentive request to HR agent")]
        elif k == "absence_review":
            steps = [PlanStep("hr.absence_decision", dict(context),
                              "Classify absence and decide action")]
        elif k in ("invoice_collection", "new_invoice"):
            steps = [
                PlanStep("finance.assess_risk", dict(context),
                         "Score payment risk via ML model"),
                PlanStep("finance.process_invoice", dict(context),
                         "Decide collection action plan"),
            ]
        elif k == "payment_received":
            steps = [PlanStep("coord.agent_handoff",
                              {"recipient": "finance_agent", "intent": "payment_received",
                               "payload": dict(context)},
                              "Route payment-received event to finance agent")]
        elif k == "risk_assessment":
            steps = [PlanStep("finance.assess_risk", dict(context),
                              "Score payment/credit risk")]
        else:
            # Generic single-shot: best-effort risk assessment if finance-ish,
            # else employee lookup, else nothing actionable.
            if context.get("invoice_id") or context.get("amount"):
                steps = [PlanStep("finance.assess_risk", dict(context),
                                  "Generic risk assessment")]
            elif context.get("employee_id"):
                steps = [PlanStep("hr.employee_lookup",
                                  {"employee_id": context.get("employee_id")},
                                  "Generic employee lookup")]

        logger.info("🗺️ [Planner] deterministic plan: %d step(s) (kind=%s)",
                    len(steps), k)
        return Plan(goal=goal, steps=steps, source="deterministic",
                    notes=f"deterministic decomposition (kind={k})")


def _safe_context(context: dict, max_len: int = 1500) -> str:
    import json
    try:
        s = json.dumps(context, default=str, ensure_ascii=False)
    except Exception:
        s = str(context)
    return s[:max_len]


_planner: Optional[GoalPlanner] = None


def get_goal_planner() -> GoalPlanner:
    global _planner
    if _planner is None:
        _planner = GoalPlanner()
    return _planner
