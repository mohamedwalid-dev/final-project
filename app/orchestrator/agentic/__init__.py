"""
🧠 Agentic Layer — Autonomous Multi-Agent Orchestration
========================================================
Package: app/orchestrator/agentic

A production-ready agentic layer that sits ON TOP of the existing
HR / Finance agents WITHOUT modifying any of them. It adds the four
capabilities of a real AI-agent system:

    1. Multi-agent coordination  → message_bus.AgentMessageBus
    2. Self-planning             → planner.GoalPlanner
    3. Tool use                  → tools.ToolRegistry + concrete tools
    4. Reflection loops          → reflection.ReflectionEngine

Everything is glued together by coordinator.AgenticCoordinator and
exposed via routes.agentic_router.

Design rules:
    - Zero edits to existing files. This package only ADDS.
    - Every LLM call has a deterministic fallback → works with no API key.
    - Fully async, thread-safe singletons, structured logging.
    - Safe by default: a failure in any layer degrades gracefully,
      it never crashes the request.
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = [
    "get_agentic_coordinator",
    "get_agent_message_bus",
    "get_tool_registry",
    "agentic_router",
]


def get_agentic_coordinator():
    from orchestrator.agentic.coordinator import get_agentic_coordinator as _f
    return _f()


def get_agent_message_bus():
    from orchestrator.agentic.message_bus import get_agent_message_bus as _f
    return _f()


def get_tool_registry():
    from orchestrator.agentic.tools import get_tool_registry as _f
    return _f()


def __getattr__(name: str):
    # Lazy router import — avoids pulling FastAPI at package import time.
    if name == "agentic_router":
        from orchestrator.agentic.routes import agentic_router
        return agentic_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
