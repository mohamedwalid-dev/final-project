"""
🧠 Agentic Coordinator — Plan → Act → Reflect Loop
===================================================
File: app/orchestrator/agentic/coordinator.py

The brain that runs the full autonomous loop on a GOAL:

    1. PLAN     — GoalPlanner decomposes the goal into tool steps.
    2. ACT      — execute each step via the ToolRegistry, threading
                  earlier outputs into later steps ($step refs).
    3. REFLECT  — ReflectionEngine critiques the run.
    4. LOOP     — accept → return | retry → re-plan (bounded) | escalate.

It also wires the existing HR / Finance agents onto the AgentMessageBus
as named inboxes, so genuine agent-to-agent coordination works (e.g. an
absence decision handing off to finance for a payroll deduction).

Everything degrades gracefully and never raises out of `run_goal`.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_ITERATIONS_DEFAULT = 2


@dataclass
class GoalRun:
    goal:        str
    run_id:      str           = field(default_factory=lambda: f"goal-{uuid.uuid4().hex[:12]}")
    status:      str           = "running"     # running | completed | escalated | failed
    iterations:  list          = field(default_factory=list)
    final:       Optional[dict] = None
    started_at:  str           = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    finished_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "run_id":      self.run_id,
            "goal":        self.goal,
            "status":      self.status,
            "iterations":  self.iterations,
            "final":       self.final,
            "started_at":  self.started_at,
            "finished_at": self.finished_at,
        }


class AgenticCoordinator:
    def __init__(self):
        self._bus_wired = False
        self._runs: dict[str, dict] = {}
        self._max_runs: int = 200

    # ── Message-bus wiring: register existing agents as inboxes ────────────────

    def wire_agents(self) -> None:
        """Register HR + Finance agents on the message bus (idempotent)."""
        if self._bus_wired:
            return
        from orchestrator.agentic.message_bus import get_agent_message_bus, AgentMessage
        bus = get_agent_message_bus()

        async def hr_inbox(msg: "AgentMessage") -> Optional[dict]:
            from agents.hr.hr_agent import HRAgent
            agent  = HRAgent()
            intent = (msg.intent or "").lower()
            data   = msg.payload or {}
            if "salary" in intent:
                return await agent.process_salary(data)
            if "absence" in intent:
                return await agent.process_absence(data)
            return await agent.async_process(data)   # default: leave

        async def finance_inbox(msg: "AgentMessage") -> Optional[dict]:
            from agents.finance.finance_agent import FinanceAgent
            agent  = FinanceAgent()
            intent = (msg.intent or "").lower()
            data   = msg.payload or {}
            if "payment" in intent:
                return await agent.process_payment_received(data)
            if "new_invoice" in intent:
                return await agent.process_new_invoice(data)
            return await agent.process_invoice(data)

        bus.register_agent("hr_agent", hr_inbox)
        bus.register_agent("finance_agent", finance_inbox)
        self._bus_wired = True
        logger.info("🧠 [Coordinator] Agents wired to message bus: hr_agent, finance_agent")

    # ── Main loop ──────────────────────────────────────────────────────────────

    async def run_goal(
        self,
        goal: str,
        context: Optional[dict] = None,
        kind: str = "",
        max_iterations: int = MAX_ITERATIONS_DEFAULT,
        request_id: str = "",
    ) -> dict:
        """
        Execute the full plan→act→reflect loop. Always returns a dict.
        """
        self.wire_agents()
        from orchestrator.agentic.planner import get_goal_planner
        from orchestrator.agentic.reflection import get_reflection_engine
        from orchestrator.agentic.tools import get_tool_registry

        context  = dict(context or {})
        run      = GoalRun(goal=goal)
        request_id = request_id or run.run_id
        planner  = get_goal_planner()
        reflector = get_reflection_engine()
        registry = get_tool_registry()

        logger.info("🧠 [Coordinator] run_goal start | run_id=%s | goal='%s'",
                    run.run_id, goal[:80])

        t0 = time.perf_counter()
        last_results: list = []
        last_reflection = None

        for iteration in range(max_iterations):
            # 1) PLAN
            plan = await planner.plan(goal, context, kind=kind)
            if not plan.steps:
                logger.warning("🧠 [Coordinator] empty plan (iter=%d) — escalating", iteration)
                run.iterations.append({
                    "iteration": iteration, "plan": plan.to_dict(),
                    "results": [], "reflection": None,
                })
                run.status = "escalated"
                break

            # 2) ACT
            results = await self._execute_plan(plan, registry, request_id)
            last_results = results

            # 3) REFLECT
            reflection = await reflector.reflect(
                goal=goal, results=results,
                iteration=iteration, max_iterations=max_iterations,
            )
            last_reflection = reflection

            run.iterations.append({
                "iteration":  iteration,
                "plan":       plan.to_dict(),
                "results":    results,
                "reflection": reflection.to_dict(),
            })

            logger.info("🧠 [Coordinator] iter=%d → reflection=%s (conf=%.2f)",
                        iteration, reflection.status, reflection.confidence)

            # 4) LOOP control
            if reflection.status == "accept":
                run.status = "completed"
                break
            if reflection.status == "escalate":
                run.status = "escalated"
                break
            # retry → enrich context with reflection suggestions, loop again
            context["_retry_hint"] = reflection.suggestions
        else:
            # ran out of iterations without accept/escalate
            run.status = "escalated" if last_reflection else "failed"

        run.final = self._synthesize(goal, last_results, last_reflection, run.status)
        run.finished_at = datetime.utcnow().isoformat() + "Z"
        run.final["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        run.final["run_id"]     = run.run_id

        self._store_run(run)
        logger.info("🧠 [Coordinator] run_goal done | run_id=%s | status=%s | %dms",
                    run.run_id, run.status, run.final["latency_ms"])
        return run.to_dict()

    # ── Step execution with output threading ──────────────────────────────────

    async def _execute_plan(self, plan, registry, request_id: str) -> list:
        results: list = []
        outputs_by_step: dict[str, dict] = {}
        ctx = {"request_id": request_id, "agent_name": "coordinator"}

        for step in plan.steps:
            args = self._resolve_refs(step.args, outputs_by_step)
            tr   = await registry.call(step.tool, args, ctx)
            rec  = tr.to_dict()
            rec["step_id"]   = step.step_id
            rec["rationale"] = step.rationale
            results.append(rec)
            outputs_by_step[step.step_id] = tr.output if isinstance(tr.output, dict) else {}
            # Also merge useful outputs forward so later steps can use them by key.
            if isinstance(tr.output, dict):
                for k in ("risk_score", "risk_label", "decision", "confidence"):
                    if k in tr.output and k not in ctx:
                        ctx[k] = tr.output[k]
        return results

    @staticmethod
    def _resolve_refs(args: dict, outputs_by_step: dict) -> dict:
        """
        Replace "$step-xxxx.field" string values in args with the actual
        output field from a prior step. Non-matching values pass through.
        """
        resolved = {}
        for k, v in (args or {}).items():
            if isinstance(v, str) and v.startswith("$"):
                try:
                    ref = v[1:]
                    step_id, _, field_name = ref.partition(".")
                    src = outputs_by_step.get(step_id, {})
                    resolved[k] = src.get(field_name, v) if field_name else src
                except Exception:
                    resolved[k] = v
            else:
                resolved[k] = v
        return resolved

    # ── Result synthesis ──────────────────────────────────────────────────────

    @staticmethod
    def _synthesize(goal, results, reflection, status: str) -> dict:
        # Pick the most informative output: last step with a 'decision'.
        primary = {}
        for r in reversed(results or []):
            out = r.get("output", {}) or {}
            if isinstance(out, dict) and out.get("decision"):
                primary = out
                break
        if not primary and results:
            primary = (results[-1].get("output") or {})

        return {
            "goal":            goal,
            "status":          status,
            "decision":        primary.get("decision"),
            "confidence":      primary.get("confidence"),
            "summary":         (reflection.reason if reflection else "No reflection"),
            "reflection":      reflection.to_dict() if reflection else None,
            "primary_output":  primary,
            "steps_executed":  len(results or []),
            "needs_human":     status in {"escalated", "failed"},
        }

    # ── Run store (introspection) ─────────────────────────────────────────────

    def _store_run(self, run: GoalRun) -> None:
        self._runs[run.run_id] = run.to_dict()
        if len(self._runs) > self._max_runs:
            oldest = next(iter(self._runs))
            self._runs.pop(oldest, None)

    def get_run(self, run_id: str) -> Optional[dict]:
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 20) -> list:
        return list(reversed(list(self._runs.values())))[:limit]

    def status(self) -> dict:
        from orchestrator.agentic.message_bus import get_agent_message_bus
        from orchestrator.agentic.tools import get_tool_registry
        from orchestrator.agentic.llm_client import get_quota_guard
        return {
            "bus_wired":     self._bus_wired,
            "tools":         get_tool_registry().names(),
            "agents":        get_agent_message_bus().registered_agents(),
            "llm_quota":     get_quota_guard().status(),
            "runs_tracked":  len(self._runs),
        }


_coordinator: Optional[AgenticCoordinator] = None


def get_agentic_coordinator() -> AgenticCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = AgenticCoordinator()
    return _coordinator
