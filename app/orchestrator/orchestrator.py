"""
🧠 Orchestrator - The Brain
وظيفته: يستقبل كل event → يحدد نوعه → يروح للـ Workflow الصح
"""

from orchestrator.workflow_registry import WorkflowRegistry
from audit.logger import AuditLogger


class Orchestrator:
    """
    المدير العام للسيستم.
    
    Flow:
        Event → identify type → find workflow → execute → return result
    """

    def __init__(self):
        self.registry = WorkflowRegistry()
        self.logger   = AuditLogger()

    # ─────────────────────────────────────────────────────────────────────────
    # Any event that enters the system enters from here. 
    def handle(self, event: dict) -> dict:
        """
        📥 Main entry: receives any event and routes it.

        Args:
            event: {
                "type": "leave_request" | "invoice_overdue" | ...,
                "payload": { ... }
            }

        Returns:
            result dict with decision + meta
        """
        event_type = event.get("type")
        payload    = event.get("payload", {})

        self.logger.log(
            event_type=event_type,
            stage="orchestrator",
            message=f"📥 Event received: {event_type}",
            data={"employee": payload.get("employee_id", "unknown")}
        )

        # ── Find the right workflow ──────────────────────────────────────────
        workflow = self.registry.get_workflow(event_type)

        if not workflow:
            error = {
                "status": "error",
                "message": f"❌ No workflow registered for event type: '{event_type}'",
                "available": self.registry.list_workflows()
            }
            self.logger.log(
                event_type=event_type,
                stage="orchestrator",
                message="❌ No workflow found",
                data=error
            )
            return error

        self.logger.log(
            event_type=event_type,
            stage="orchestrator",
            message=f"✅ Routing to: {workflow.__class__.__name__}"
        )

        # ── Execute the workflow (sync) ──────────────────────────────────────
        result = workflow.run(payload)

        self.logger.log(
            event_type=event_type,
            stage="orchestrator",
            message="🏁 Pipeline complete",
            data={"decision": result.get("decision"), "confidence": result.get("confidence")}
        )

        return result

    # ─────────────────────────────────────────────────────────────────────────
    async def async_handle(self, event: dict) -> dict:
        """
        📥 Async entry point — used by FastAPI async endpoints.
        Routes to workflow.async_run() if available, else falls back to sync run().
        """
        event_type = event.get("type")
        payload    = event.get("payload", {})

        self.logger.log(
            event_type=event_type,
            stage="orchestrator",
            message=f"📥 Async event received: {event_type}",
            data={"employee": payload.get("employee_id", "unknown")}
        )

        workflow = self.registry.get_workflow(event_type)

        if not workflow:
            error = {
                "status":    "error",
                "message":   f"❌ No workflow registered for event type: '{event_type}'",
                "available": self.registry.list_workflows()
            }
            self.logger.log(
                event_type=event_type,
                stage="orchestrator",
                message="❌ No workflow found",
                data=error
            )
            return error

        self.logger.log(
            event_type=event_type,
            stage="orchestrator",
            message=f"✅ Routing to: {workflow.__class__.__name__}"
        )

        # Use async_run if the workflow supports it
        if hasattr(workflow, "async_run"):
            result = await workflow.async_run(payload)
        else:
            result = workflow.run(payload)

        self.logger.log(
            event_type=event_type,
            stage="orchestrator",
            message="🏁 Async pipeline complete",
            data={"decision": result.get("decision"), "confidence": result.get("confidence")}
        )

        return result
