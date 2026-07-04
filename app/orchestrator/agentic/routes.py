"""
🌐 Agentic API Routes
=====================
File: app/orchestrator/agentic/routes.py

FastAPI router exposing the agentic layer. Mounted under /agentic in main.py.

Endpoints:
    POST /agentic/goal            → run the full plan→act→reflect loop
    POST /agentic/plan            → dry-run: return the plan only (no execution)
    GET  /agentic/runs            → recent goal runs
    GET  /agentic/runs/{run_id}   → one run's full trace
    GET  /agentic/tools           → tool catalog
    POST /agentic/message         → send an agent-to-agent message (request/reply)
    GET  /agentic/messages        → recent message-bus history
    GET  /agentic/status          → coordinator + bus + quota status
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

agentic_router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class GoalRequest(BaseModel):
    goal:           str  = Field(..., description="High-level goal in natural language")
    context:        dict = Field(default_factory=dict, description="Input data for tool args")
    kind:           str  = Field("", description="Optional hint: leave_review|salary_review|absence_review|invoice_collection|risk_assessment")
    max_iterations: int  = Field(2, ge=1, le=5)


class MessageRequest(BaseModel):
    sender:    str   = Field("api_client")
    recipient: str   = Field(..., description="Registered agent name, e.g. hr_agent | finance_agent")
    intent:    str   = Field(..., description="What you want the agent to do")
    payload:   dict  = Field(default_factory=dict)
    timeout:   float = Field(30.0, ge=1.0, le=120.0)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@agentic_router.post("/goal", tags=["🧠 Agentic"])
async def run_agentic_goal(body: GoalRequest):
    """Run the autonomous plan→act→reflect loop on a goal."""
    from orchestrator.agentic.coordinator import get_agentic_coordinator
    coord  = get_agentic_coordinator()
    result = await coord.run_goal(
        goal=body.goal,
        context=body.context,
        kind=body.kind,
        max_iterations=body.max_iterations,
    )
    return result


@agentic_router.post("/plan", tags=["🧠 Agentic"])
async def plan_only(body: GoalRequest):
    """Dry-run: return the plan the agent WOULD execute, without running it."""
    from orchestrator.agentic.planner import get_goal_planner
    plan = await get_goal_planner().plan(body.goal, body.context, kind=body.kind)
    return plan.to_dict()


@agentic_router.get("/runs", tags=["🧠 Agentic"])
async def list_agentic_runs(limit: int = 20):
    from orchestrator.agentic.coordinator import get_agentic_coordinator
    runs = get_agentic_coordinator().list_runs(limit=limit)
    return {"count": len(runs), "runs": runs}


@agentic_router.get("/runs/{run_id}", tags=["🧠 Agentic"])
async def get_agentic_run(run_id: str):
    from orchestrator.agentic.coordinator import get_agentic_coordinator
    run = get_agentic_coordinator().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@agentic_router.get("/tools", tags=["🧠 Agentic"])
async def list_tools():
    from orchestrator.agentic.tools import get_tool_registry
    reg = get_tool_registry()
    return {"count": len(reg.names()), "tools": reg.specs()}


@agentic_router.post("/message", tags=["🧠 Agentic"])
async def send_agent_message(body: MessageRequest):
    """Send a correlated agent-to-agent message and await the reply."""
    from orchestrator.agentic.coordinator import get_agentic_coordinator
    from orchestrator.agentic.message_bus import get_agent_message_bus
    get_agentic_coordinator().wire_agents()    # ensure inboxes are registered
    bus   = get_agent_message_bus()
    reply = await bus.request(
        sender=body.sender, recipient=body.recipient,
        intent=body.intent, payload=body.payload, timeout=body.timeout,
    )
    if reply is None:
        raise HTTPException(
            status_code=504,
            detail=f"No reply from '{body.recipient}' (unknown agent or timeout).",
        )
    return {"recipient": body.recipient, "intent": body.intent, "reply": reply}


@agentic_router.get("/messages", tags=["🧠 Agentic"])
async def message_history(correlation_id: Optional[str] = None, limit: int = 50):
    from orchestrator.agentic.message_bus import get_agent_message_bus
    bus = get_agent_message_bus()
    return {
        "history": bus.get_history(correlation_id=correlation_id, limit=limit),
        "stats":   bus.get_stats(),
    }


@agentic_router.get("/status", tags=["🧠 Agentic"])
async def agentic_status():
    from orchestrator.agentic.coordinator import get_agentic_coordinator
    return get_agentic_coordinator().status()
