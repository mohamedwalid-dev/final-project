"""
🗄️ Agentic Run Store — Durable Goal-Run Persistence
====================================================
File: app/orchestrator/agentic/run_store.py

Persists every agentic goal run to MongoDB so the plan→act→reflect trace
survives restarts and joins the rest of the system's audit trail.

Mirrors the project's existing DB pattern exactly:
    hr_db = get_hr_db()
    await hr_db.db["agentic_runs"].insert_one(doc)

Graceful degradation (same philosophy as the rest of the codebase):
    - If Mongo is unavailable, every operation falls back to a bounded
      in-memory ring buffer and logs at debug level. The agentic loop never
      fails because persistence is down.
    - Reads merge the in-memory buffer with Mongo so a run is visible
      immediately even if the async DB write is still in flight / failed.

Collection: "agentic_runs"  (keyed by run_id)
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)

COLLECTION = "agentic_runs"
_MEM_CAP   = 200


class AgenticRunStore:
    def __init__(self):
        # run_id → run dict (most-recent-last). Always the freshest copy.
        self._mem: "OrderedDict[str, dict]" = OrderedDict()
        self._lock = asyncio.Lock()
        self._api_ok = True   # flips to False after a failure; retried lazily

    # ── Write ──────────────────────────────────────────────────────────────

    async def save(self, run: dict) -> None:
        """Upsert a run by run_id. Memory first (always), Mongo best-effort."""
        run_id = run.get("run_id")
        if not run_id:
            return

        async with self._lock:
            self._mem[run_id] = run
            self._mem.move_to_end(run_id)
            while len(self._mem) > _MEM_CAP:
                self._mem.popitem(last=False)

        await self._api_upsert(run_id, run)

    async def _api_upsert(self, run_id: str, run: dict) -> None:
        try:
            from core.node_api_client import get_node_api_client
            client = get_node_api_client()
            
            from datetime import datetime
            doc = {**run, "run_id": run_id, "_updated_at": datetime.utcnow().isoformat()}
            
            # Upsert via Node API
            await client.update_resource(f"/agentic-runs/{run_id}", doc, method="PUT")
            self._api_ok = True
        except Exception as e:
            if getattr(self, "_api_ok", True):
                logger.debug("🗄️ [RunStore] API upsert failed (using memory): %s", e)
            self._api_ok = False

    # ── Read ───────────────────────────────────────────────────────────────

    async def get(self, run_id: str) -> Optional[dict]:
        async with self._lock:
            if run_id in self._mem:
                return self._mem[run_id]
        # Fall through to API for older runs evicted from memory.
        try:
            from core.node_api_client import get_node_api_client
            client = get_node_api_client()
            return await client._request("GET", f"/agentic-runs/{run_id}")
        except Exception as e:
            logger.debug("🗄️ [RunStore] API get failed: %s", e)
            return None

    async def list(self, limit: int = 20) -> list:
        """Most-recent-first. Merges API (durable) with memory (freshest)."""
        out: "OrderedDict[str, dict]" = OrderedDict()

        # 1) API first (older + durable)
        try:
            from core.node_api_client import get_node_api_client
            client = get_node_api_client()
            docs = await client._request("GET", f"/agentic-runs?limit={limit}")
            if isinstance(docs, list):
                for doc in docs:
                    rid = doc.get("run_id")
                    if rid:
                        out[rid] = doc
        except Exception as e:
            logger.debug("🗄️ [RunStore] API list failed (memory only): %s", e)

        # 2) Overlay memory copies (freshest wins).
        async with self._lock:
            for rid, run in reversed(self._mem.items()):
                out[rid] = run

        runs = list(out.values())
        # Sort newest-first by started_at when present.
        runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
        return runs[:limit]

    # ── Helpers ──────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "collection":   COLLECTION,
            "api_ok":       getattr(self, "_api_ok", True),
            "mem_buffered": len(self._mem),
            "mem_cap":      _MEM_CAP,
        }


_store: Optional[AgenticRunStore] = None


def get_run_store() -> AgenticRunStore:
    global _store
    if _store is None:
        _store = AgenticRunStore()
    return _store
