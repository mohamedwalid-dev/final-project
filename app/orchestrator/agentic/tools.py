"""
🛠️ Tool Registry + Concrete Tools — Agentic Layer
==================================================
File: app/orchestrator/agentic/tools.py

Tools are the only way an agent acts on the world. Each tool wraps an
EXISTING capability of the system (an agent, the DB, the email service,
the message bus) behind a uniform async contract:

    async def run(args: dict, ctx: dict) -> ToolResult

The registry exposes machine-readable specs (name, description, args)
so the planner can decide which tools to call — and so /agentic/tools
can list them for humans.

Nothing here re-implements business logic: it DELEGATES to the existing
HRAgent / FinanceAgent / FinanceActionExecutor / EmailService. If a
dependency is missing at runtime, the tool degrades to a safe error
ToolResult instead of raising.

────────────────────────────────────────────────────────────────────────
✅ FIX (2026-07): NODE_API_TOOLS integration
────────────────────────────────────────────────────────────────────────
main.py's startup log used to warn:

    "⚠️ Agentic coordinator has no register_tools() method —
     NODE_API_TOOLS was NOT auto-registered."

Root cause: agents/tools/node_api_tools.py exposes LangChain @tool
functions (async, JSON-string output) — a completely different shape
from this file's own `Tool` dataclass (sync-looking `fn(args, ctx) ->
ToolResult` contract). There was never a compatible place to register
them, so main.py's attempted `coordinator.register_tools(...)` call
was reaching for a method that intentionally never existed on
AgenticCoordinator — the right home for tool registration is (and was
always meant to be) THIS registry, not the coordinator.

Fix: `_wrap_langchain_tool()` adapts any LangChain BaseTool into this
file's `Tool` shape (extracts name/description/args_schema from the
LangChain tool itself, calls `.ainvoke()` under the hood, and parses
the JSON-string result back into a dict so `$step.field` output-
threading in coordinator.py keeps working transparently). All tools in
NODE_API_TOOLS are auto-registered under a `node_api.` prefix so they
never collide with the hand-written tools below (e.g. `finance.
process_invoice` vs `node_api.get_invoices` are clearly distinguishable
to the planner). main.py no longer needs to call anything — this
happens automatically the first time get_tool_registry() is called.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


# ── Result envelope ───────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    ok:          bool
    tool:        str
    output:      dict          = field(default_factory=dict)
    error:       Optional[str] = None
    latency_ms:  int           = 0

    def to_dict(self) -> dict:
        return {
            "ok":         self.ok,
            "tool":       self.tool,
            "output":     self.output,
            "error":      self.error,
            "latency_ms": self.latency_ms,
        }


# ── Tool spec ─────────────────────────────────────────────────────────────────

ToolFn = Callable[[dict, dict], Awaitable[ToolResult]]


@dataclass
class Tool:
    name:        str
    description: str
    args_schema: dict          # {arg_name: "description"} — for the planner/LLM
    fn:          ToolFn
    category:    str = "general"

    def spec(self) -> dict:
        return {
            "name":        self.name,
            "description": self.description,
            "args":        self.args_schema,
            "category":    self.category,
        }

    async def run(self, args: dict, ctx: dict) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = await self.fn(args or {}, ctx or {})
            result.latency_ms = int((time.perf_counter() - t0) * 1000)
            return result
        except Exception as e:
            logger.error("🛠️ [Tool:%s] failed: %s", self.name, e, exc_info=True)
            return ToolResult(
                ok=False, tool=self.name, error=str(e)[:300],
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )


# ── Registry ──────────────────────────────────────────────────────────────────

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.debug("🛠️ [ToolRegistry] registered '%s'", tool.name)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def specs(self) -> list[dict]:
        return [t.spec() for t in self._tools.values()]

    def specs_text(self) -> str:
        """Compact catalog string for embedding into an LLM planning prompt."""
        lines = []
        for t in self._tools.values():
            args = ", ".join(f"{k} ({v})" for k, v in t.args_schema.items()) or "none"
            lines.append(f"- {t.name}: {t.description} | args: {args}")
        return "\n".join(lines)

    async def call(self, name: str, args: dict, ctx: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                ok=False, tool=name,
                error=f"Unknown tool '{name}'. Available: {self.names()}",
            )
        return await tool.run(args, ctx)


# ══════════════════════════════════════════════════════════════════════════════
# Concrete tools — each DELEGATES to an existing capability
# ══════════════════════════════════════════════════════════════════════════════

# ── HR: leave decision ────────────────────────────────────────────────────────

async def _tool_hr_leave_decision(args: dict, ctx: dict) -> ToolResult:
    from agents.hr.hr_agent import HRAgent
    agent  = HRAgent()
    result = await agent.async_process(args)
    return ToolResult(ok=True, tool="hr.leave_decision", output=result)


async def _tool_hr_salary_decision(args: dict, ctx: dict) -> ToolResult:
    from agents.hr.hr_agent import HRAgent
    agent  = HRAgent()
    result = await agent.process_salary(args)
    return ToolResult(ok=True, tool="hr.salary_decision", output=result)


async def _tool_hr_absence_decision(args: dict, ctx: dict) -> ToolResult:
    from agents.hr.hr_agent import HRAgent
    agent  = HRAgent()
    result = await agent.process_absence(args)
    return ToolResult(ok=True, tool="hr.absence_decision", output=result)


# ── Finance: risk assessment ──────────────────────────────────────────────────

async def _tool_finance_assess_risk(args: dict, ctx: dict) -> ToolResult:
    from agents.finance.risk_model_handler import get_finance_risk_handler
    handler = get_finance_risk_handler()
    # handler.predict is sync + CPU-bound (XGBoost) → run off the event loop
    import asyncio
    result = await asyncio.to_thread(handler.predict, args, ctx.get("request_id", ""))
    return ToolResult(ok=True, tool="finance.assess_risk", output=result)


async def _tool_finance_process_invoice(args: dict, ctx: dict) -> ToolResult:
    from agents.finance.finance_agent import FinanceAgent
    agent  = FinanceAgent()
    result = await agent.process_invoice(args)
    return ToolResult(ok=True, tool="finance.process_invoice", output=result)


# ── Finance: execute a collection action (email/escalation/...) ───────────────

async def _tool_finance_execute_action(args: dict, ctx: dict) -> ToolResult:
    from actions.finance_actions import FinanceActionExecutor
    executor = FinanceActionExecutor()
    result = await executor.execute(
        action      = args.get("action", "send_polite_reminder"),
        invoice_id  = args.get("invoice_id"),
        customer_id = args.get("customer_id"),
        amount      = float(args.get("amount", 0) or 0),
        decision    = args.get("decision", "agentic_trigger"),
        reason      = args.get("reason", "Triggered by agentic coordinator"),
        request_id  = ctx.get("request_id", "agentic"),
        extra_data  = args.get("extra_data"),
    )
    return ToolResult(ok=True, tool="finance.execute_action", output=result or {})


# ── Email ─────────────────────────────────────────────────────────────────────

async def _tool_send_email(args: dict, ctx: dict) -> ToolResult:
    from core.email_service import EmailService
    svc    = EmailService()
    result = await svc.send_email(
        to_email = args.get("to_email", ""),
        subject  = args.get("subject", "(no subject)"),
        body     = args.get("body", ""),
    )
    return ToolResult(ok=bool(result), tool="comms.send_email", output=result or {})


# ── HR DB lookup (read-only) ──────────────────────────────────────────────────
#
# ⚠️ DISABLED (2026-07): there is no GET /hr/employees/:id route in
# hr.routes.js — node_hr_proxy.py's own module docstring confirms this
# explicitly ("لا يوجد /hr/employees ... راجع hr.routes.js"). Calling
# client._request("GET", f"/hr/employees/{emp_id}") therefore always
# hit a 404 → NodeAPIError → an opaque failure that looked like a bug
# in THIS tool rather than a genuinely missing backend route.
#
# Rather than silently keep sending doomed requests (which also trips
# the NodeAPIClient circuit breaker after NODE_API_CB_FAILURE_THRESHOLD
# consecutive 404s and starts failing OTHER node_api.* tools for
# NODE_API_CB_COOLDOWN_SEC), this tool now fails fast with a clear,
# actionable error and is excluded from the default registry below.
#
# To re-enable: add `router.get('/employees/:id', ...)` (and a
# matching controller) to hr.routes.js, then move this tool's
# `reg.register(...)` call back into `_build_default_registry()`.
async def _tool_hr_employee_lookup(args: dict, ctx: dict) -> ToolResult:
    emp_id = str(args.get("employee_id", ""))
    return ToolResult(
        ok=False,
        tool="hr.employee_lookup",
        error=(
            f"hr.employee_lookup is disabled: GET /hr/employees/{emp_id} "
            "does not exist in hr.routes.js (no employee-by-id route is "
            "registered on the Node.js side yet). Add the route + "
            "controller in Node first, then re-enable this tool in "
            "orchestrator/agentic/tools.py. In the meantime, employee "
            "context can be approximated via node_api.get_leave_by_id / "
            "node_api.get_absence_event_by_id / node_api.get_salary_review_by_id "
            "if you already have a leave/absence/salary-review id for them."
        ),
    )


# ── Agent-to-agent handoff (via message bus) ──────────────────────────────────

async def _tool_agent_handoff(args: dict, ctx: dict) -> ToolResult:
    from orchestrator.agentic.message_bus import get_agent_message_bus
    bus   = get_agent_message_bus()
    reply = await bus.request(
        sender    = ctx.get("agent_name", "coordinator"),
        recipient = args.get("recipient", ""),
        intent    = args.get("intent", "handoff"),
        payload   = args.get("payload", {}),
        timeout   = float(args.get("timeout", 30.0)),
    )
    if reply is None:
        return ToolResult(ok=False, tool="coord.agent_handoff",
                          error=f"No reply from '{args.get('recipient')}'")
    return ToolResult(ok=True, tool="coord.agent_handoff", output=reply)


# ══════════════════════════════════════════════════════════════════════════════
# ✅ NEW: LangChain → Tool adapter for agents/tools/node_api_tools.py
# ══════════════════════════════════════════════════════════════════════════════
#
# NODE_API_TOOLS is a list of LangChain @tool-decorated async callables
# (see agents/tools/node_api_tools.py). Each one:
#   - is invoked as `await lc_tool.ainvoke(kwargs_dict)`, not `fn(args, ctx)`
#   - returns a JSON *string* (via _ok()/_err() → json.dumps), not a dict
#   - already carries its own name/description/args schema (introspectable
#     via lc_tool.name / lc_tool.description / lc_tool.args)
#
# _wrap_langchain_tool() bridges that into this registry's `Tool` shape so
# the planner can call these exactly like any hand-written tool above,
# and so `$step.field` output-threading in coordinator.py's
# _execute_plan()/_resolve_refs() keeps working (it expects
# ToolResult.output to already be a dict).

def _wrap_langchain_tool(lc_tool: Any, *, name_prefix: str = "node_api.") -> Tool:
    """Adapt one LangChain BaseTool into this module's Tool contract."""

    wrapped_name = f"{name_prefix}{lc_tool.name}"

    # LangChain tools expose their args schema in a few different shapes
    # depending on version (pydantic v1 vs v2 models, or a plain dict on
    # older StructuredTool instances). Try the common ones defensively —
    # falling back to an empty schema is safe, it just means the planner
    # gets a slightly less detailed catalog entry, not a crash.
    args_schema: dict = {}
    try:
        raw_args = getattr(lc_tool, "args", None)  # dict[str, dict] on most versions
        if isinstance(raw_args, dict):
            for arg_name, arg_spec in raw_args.items():
                if isinstance(arg_spec, dict):
                    desc = arg_spec.get("description") or arg_spec.get("type") or "value"
                else:
                    desc = str(arg_spec)
                args_schema[arg_name] = desc
    except Exception as e:
        logger.debug("🛠️ [node_api adapter] could not introspect args for '%s': %s",
                     lc_tool.name, e)

    async def _fn(args: dict, ctx: dict) -> ToolResult:
        try:
            raw = await lc_tool.ainvoke(args or {})
        except Exception as e:
            logger.warning("🛠️ [node_api adapter] '%s' ainvoke failed: %s", wrapped_name, e)
            return ToolResult(ok=False, tool=wrapped_name, error=str(e)[:300])

        # node_api_tools._ok()/_err() always return a JSON string.
        # Parse it back into a dict so downstream output-threading works;
        # if it's ever not valid JSON (shouldn't happen, but tools can
        # change), fall back to wrapping the raw string.
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                parsed = {"raw": raw}
        elif isinstance(raw, dict):
            parsed = raw
        else:
            parsed = {"raw": raw}

        # node_api_tools wraps every result as {"ok": bool, "data"|"error": ...}
        # — surface that as this ToolResult's own ok/error so a failed Node
        # API call (e.g. 404/401/circuit-open) is visible to the reflector
        # as a genuine failure, not a "successful" call that happens to
        # contain an error field.
        if isinstance(parsed, dict) and "ok" in parsed:
            ok = bool(parsed.get("ok"))
            return ToolResult(
                ok=ok,
                tool=wrapped_name,
                output=parsed if ok else {},
                error=None if ok else str(parsed.get("error", "node API call failed"))[:300],
            )

        return ToolResult(ok=True, tool=wrapped_name, output=parsed)

    return Tool(
        name=wrapped_name,
        description=(lc_tool.description or f"Node.js ERP API: {lc_tool.name}").strip(),
        args_schema=args_schema,
        fn=_fn,
        category="node_api",
    )


def _register_node_api_tools(reg: ToolRegistry) -> int:
    """Import agents.tools.node_api_tools.NODE_API_TOOLS and register each
    one, wrapped, under the registry. Degrades gracefully (logs + returns
    0) if the module or its dependencies (e.g. langchain_core) aren't
    importable in a given environment, instead of failing app startup."""
    try:
        from agents.tools.node_api_tools import NODE_API_TOOLS
    except Exception as e:
        logger.warning(
            "⚠️ [ToolRegistry] Could not import NODE_API_TOOLS — skipping "
            "auto-registration (%s)", e,
        )
        return 0

    count = 0
    for lc_tool in NODE_API_TOOLS:
        try:
            reg.register(_wrap_langchain_tool(lc_tool))
            count += 1
        except Exception as e:
            logger.warning(
                "⚠️ [ToolRegistry] Failed to wrap/register NODE_API_TOOLS "
                "tool '%s': %s", getattr(lc_tool, "name", "?"), e,
            )
    return count


# ── Build the default registry ────────────────────────────────────────────────

def _build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(Tool(
        name="hr.leave_decision", category="hr",
        description="Run the HR AI agent (ML + Gemini) on a leave request and return its decision.",
        args_schema={"employee_id": "str", "requested_days": "int",
                     "leave_balance": "int", "leave_type": "str"},
        fn=_tool_hr_leave_decision,
    ))
    reg.register(Tool(
        name="hr.salary_decision", category="hr",
        description="Run the salary decision engine for a salary-review payload.",
        args_schema={"employee_id": "str", "current_salary_egp": "float",
                     "performance_score": "float", "kpi_achievement": "float"},
        fn=_tool_hr_salary_decision,
    ))
    reg.register(Tool(
        name="hr.absence_decision", category="hr",
        description="Classify an absence event and decide warning / deduction / escalation.",
        args_schema={"employee_id": "str", "absence_type_claimed": "str",
                     "unexcused_count_90d": "int", "performance_score": "float"},
        fn=_tool_hr_absence_decision,
    ))
    # ⚠️ hr.employee_lookup intentionally NOT registered — see the
    # _tool_hr_employee_lookup docstring above: GET /hr/employees/:id
    # does not exist in hr.routes.js yet. Re-add the line below once
    # that route + controller exist on the Node side:
    #
    # reg.register(Tool(
    #     name="hr.employee_lookup", category="hr",
    #     description="Read-only lookup of an employee record from MongoDB by id.",
    #     args_schema={"employee_id": "str"},
    #     fn=_tool_hr_employee_lookup,
    # ))
    reg.register(Tool(
        name="finance.assess_risk", category="finance",
        description="Score payment/credit risk for an invoice using the ML risk model.",
        args_schema={"overdue_days": "float", "amount": "float",
                     "credit_score": "float", "industry": "str"},
        fn=_tool_finance_assess_risk,
    ))
    reg.register(Tool(
        name="finance.process_invoice", category="finance",
        description="Full overdue-invoice pipeline (hard rules → ML → LLM → action plan).",
        args_schema={"invoice_id": "str", "customer_id": "str",
                     "amount": "float", "overdue_days": "int"},
        fn=_tool_finance_process_invoice,
    ))
    reg.register(Tool(
        name="finance.execute_action", category="finance",
        description="Execute a concrete collection action (reminder/notice/escalation/receipt).",
        args_schema={"action": "str", "invoice_id": "str", "customer_id": "str",
                     "amount": "float", "reason": "str"},
        fn=_tool_finance_execute_action,
    ))
    reg.register(Tool(
        name="comms.send_email", category="comms",
        description="Send an email via the system email service.",
        args_schema={"to_email": "str", "subject": "str", "body": "str"},
        fn=_tool_send_email,
    ))
    reg.register(Tool(
        name="coord.agent_handoff", category="coordination",
        description="Hand a sub-task to another registered agent and await its reply.",
        args_schema={"recipient": "str", "intent": "str", "payload": "dict"},
        fn=_tool_agent_handoff,
    ))

    # ✅ Auto-register every tool from agents/tools/node_api_tools.py,
    # wrapped to this registry's contract, under the "node_api." prefix
    # (e.g. node_api.get_overdue_invoices, node_api.get_hr_dashboard_stats).
    # This is what used to be attempted (and fail) via a non-existent
    # coordinator.register_tools() call in main.py — see this file's
    # module docstring for the full root-cause explanation.
    n = _register_node_api_tools(reg)
    logger.info("🛠️ [ToolRegistry] auto-registered %d NODE_API_TOOLS under 'node_api.*'", n)

    return reg


# ── Singleton ─────────────────────────────────────────────────────────────────
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = _build_default_registry()
    return _registry