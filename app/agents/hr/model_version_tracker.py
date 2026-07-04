"""
📦 Model Version Tracker — v3.0 Production (Filesystem-only)
=====================================================
File: app/agents/hr/model_version_tracker.py

⚠️ MIGRATION NOTE (v2.0 → v3.0):
    v2.0 stored version records in MongoDB via core.node_hr_proxy.get_hr_db()
    ("model_versions" collection, direct Motor/PyMongo-style calls).

    That direct MongoDB access has been removed. The project's HR data now
    goes through the Node.js/Express API (see core/node_api_client.py +
    hr.routes.js), and that API does NOT currently expose any
    /hr/model-versions endpoint — so there's nothing to point this at yet.

    Rather than invent an endpoint that doesn't exist on the Node side
    (which would just fail with 404s), this version tracks everything on
    the local filesystem only:
        - Each version's artifacts are copied into versions/vN/ (unchanged
          from v2.0).
        - A single JSON index file (versions/_index.json) replaces the
          MongoDB collection — it holds the same fields the DB used to
          (version, accuracy, roc_auc, f1_score, trained_at, is_active, ...).
        - list_versions() / get_active_version() now read from that index
          instead of awaiting a DB call.

    All public method signatures are unchanged (still async, same params,
    same return shapes) so callers (training pipeline, /model/versions
    endpoint, rollback flow) do not need to change.

    🔜 TODO once the Node side adds model-version endpoints (e.g.
    POST /hr/model-versions, GET /hr/model-versions, PATCH
    /hr/model-versions/:version/activate): swap _read_index() /
    _write_index() / _set_active_in_index() for calls through
    core.node_api_client.get_node_api_client(), the same way
    core/node_hr_proxy.py does for leaves/salary/absence/incentive.

🎯 Responsibilities:
    1. Save each trained model with a versioned filename (model_v1.pkl, model_v2.pkl, ...)
    2. Track all versions in a local JSON index (versions/_index.json)
    3. Allow rollback to any previous version
    4. Expose version history for /model/versions endpoint
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE        = Path(__file__).resolve().parent.parent.parent
MODEL_DIR    = _BASE / "app" / "models" / "hr"
VERSIONS_DIR = MODEL_DIR / "versions"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

ACTIVE_MODEL_PATH   = MODEL_DIR / "leave_approval_model.pkl"
ACTIVE_SCALER_PATH  = MODEL_DIR / "scaler.pkl"
ACTIVE_ENCODER_PATH = MODEL_DIR / "encoders.pkl"
ACTIVE_META_PATH    = MODEL_DIR / "model_metadata.json"

# Local JSON index — replaces the old MongoDB "model_versions" collection.
INDEX_PATH = VERSIONS_DIR / "_index.json"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ════════════════════════════════════════════════════════════════════════════
# 📦  MODEL VERSION TRACKER
# ════════════════════════════════════════════════════════════════════════════

class ModelVersionTracker:
    """
    Tracks ML model versions with filesystem snapshots + a local JSON index.

    Usage (from training pipeline):
        tracker = get_version_tracker()
        version = await tracker.save_new_version(metadata)

    Usage (rollback):
        await tracker.rollback_to_version(version=2)
    """

    def __init__(self):
        self._lock = threading.Lock()

    # ── Index I/O (replaces the old MongoDB collection) ─────────────────────

    def _read_index(self) -> list[dict]:
        """Load the local version index. Returns [] if it doesn't exist yet
        or is corrupted (never raises — this is a read path)."""
        if not INDEX_PATH.exists():
            return []
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning("⚠️ [ModelVersionTracker] Failed to read index: %s", e)
            return []

    def _write_index(self, records: list[dict]) -> None:
        """Persist the local version index (atomic-ish via tmp file + replace)."""
        tmp_path = INDEX_PATH.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False, default=str)
        tmp_path.replace(INDEX_PATH)

    def _upsert_index_record(self, record: dict) -> None:
        """Insert or update a version record by 'version', deactivating all
        others (mirrors the old col.update_many({}, {is_active: False}) +
        upsert behavior)."""
        records = self._read_index()
        for r in records:
            r["is_active"] = False

        found = False
        for i, r in enumerate(records):
            if r.get("version") == record.get("version"):
                records[i] = record
                found = True
                break
        if not found:
            records.append(record)

        self._write_index(records)

    def _set_active_in_index(self, version: int) -> None:
        records = self._read_index()
        for r in records:
            r["is_active"] = (r.get("version") == version)
        self._write_index(records)

    # ── Public API ────────────────────────────────────────────────────────────

    async def save_new_version(self, metadata: dict) -> int:
        """
        Snapshot the current active model files as a new version.
        Called right after training completes and artifacts are saved.

        Returns:
            New version number (int).
        """
        with self._lock:
            next_version = self._get_next_version()
            version_dir  = VERSIONS_DIR / f"v{next_version}"
            version_dir.mkdir(parents=True, exist_ok=True)

            # Copy active artifacts → versioned directory
            copied = []
            for src in [ACTIVE_MODEL_PATH, ACTIVE_SCALER_PATH, ACTIVE_ENCODER_PATH, ACTIVE_META_PATH]:
                if src.exists():
                    dst = version_dir / src.name
                    shutil.copy2(src, dst)
                    copied.append(src.name)

            if not copied:
                logger.warning("⚠️ [ModelVersionTracker] No active model files found to snapshot.")
                return 0

            snapshot_meta = {
                "version":  next_version,
                "saved_at": _utcnow().isoformat(),
                "files":    copied,
                **metadata,
            }
            meta_snapshot = version_dir / "version_metadata.json"
            with open(meta_snapshot, "w", encoding="utf-8") as f:
                json.dump(snapshot_meta, f, indent=2, ensure_ascii=False)

            self._record_in_index(next_version, metadata, snapshot_meta)

            logger.info(
                "📦 [ModelVersionTracker] Saved model v%d → %s | accuracy=%s | AUC=%s",
                next_version,
                version_dir,
                metadata.get("evaluation", {}).get("accuracy", "?"),
                metadata.get("evaluation", {}).get("roc_auc", "?"),
            )

            return next_version

    async def rollback_to_version(self, version: int) -> bool:
        """
        Restore a previously saved model version as the active model.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        version_dir = VERSIONS_DIR / f"v{version}"
        if not version_dir.exists():
            logger.error(
                "❌ [ModelVersionTracker] Version v%d not found at %s",
                version, version_dir,
            )
            return False

        with self._lock:
            restored = []
            for src in version_dir.glob("*.pkl"):
                dst_map = {
                    "leave_approval_model.pkl": ACTIVE_MODEL_PATH,
                    "scaler.pkl":               ACTIVE_SCALER_PATH,
                    "encoders.pkl":             ACTIVE_ENCODER_PATH,
                }
                dst = dst_map.get(src.name)
                if dst:
                    shutil.copy2(src, dst)
                    restored.append(src.name)

            src_meta = version_dir / "model_metadata.json"
            if src_meta.exists():
                shutil.copy2(src_meta, ACTIVE_META_PATH)
                restored.append("model_metadata.json")

            if not restored:
                logger.error("❌ [ModelVersionTracker] No files restored for v%d.", version)
                return False

            self._set_active_in_index(version)

            logger.info(
                "✅ [ModelVersionTracker] Rolled back to v%d | files: %s",
                version, restored,
            )
            return True

    async def list_versions(self, limit: int = 20) -> list[dict]:
        """Return version history (newest first) from the local index, with
        a filesystem-derived fallback if the index is empty/missing."""
        records = self._read_index()
        if records:
            records_sorted = sorted(records, key=lambda r: r.get("version", 0), reverse=True)
            return records_sorted[:limit]
        return self._list_from_filesystem()[:limit]

    async def get_active_version(self) -> Optional[dict]:
        """Return info about the currently active model version."""
        records = self._read_index()
        active = [r for r in records if r.get("is_active")]
        if not active:
            return None
        active.sort(key=lambda r: r.get("version", 0), reverse=True)
        return active[0]

    def get_version_info(self, version: int) -> Optional[dict]:
        """Return metadata for a specific version (filesystem only)."""
        meta_path = VERSIONS_DIR / f"v{version}" / "version_metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _get_next_version(self) -> int:
        """Compute next version number from existing directories."""
        existing = [
            int(d.name[1:])
            for d in VERSIONS_DIR.iterdir()
            if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()
        ]
        return max(existing, default=0) + 1

    def _record_in_index(self, version: int, metadata: dict, snapshot_meta: dict) -> None:
        """Insert (or update) a version record in the local JSON index.
        Mirrors the old MongoDB _record_in_db() shape/fields exactly, minus
        the DB round-trip."""
        try:
            eval_m = metadata.get("evaluation", {})
            cost_m = metadata.get("business_costs", {})

            record = {
                "version":      version,
                "filename":     f"leave_approval_model_v{version}.pkl",
                "data_source":  metadata.get("data_source", "unknown"),
                "accuracy":     eval_m.get("accuracy"),
                "roc_auc":      eval_m.get("roc_auc"),
                "f1_score":     eval_m.get("f1_score"),
                "monthly_cost": cost_m.get("monthly_cost_egp"),
                "trained_at":   _utcnow().isoformat(),
                "is_active":    True,
                "notes":        {
                    "n_samples":   metadata.get("n_training_samples"),
                    "thresholds":  metadata.get("thresholds"),
                    "saved_files": snapshot_meta.get("files", []),
                },
                "created_at":   _utcnow().isoformat(),
            }

            self._upsert_index_record(record)
        except Exception as e:
            logger.warning(
                "⚠️ [ModelVersionTracker] Index record failed (non-critical): %s. "
                "Version still saved to filesystem (versions/vN/).",
                e,
            )

    def _list_from_filesystem(self) -> list[dict]:
        """Fallback: list versions purely from filesystem when the index is
        missing/empty (e.g. first run, or index file was deleted)."""
        versions = []
        for d in sorted(VERSIONS_DIR.iterdir(), reverse=True):
            if not (d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()):
                continue
            meta_path = d / "version_metadata.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                eval_m = meta.get("evaluation", {})
                versions.append({
                    "version":     meta.get("version"),
                    "data_source": meta.get("data_source"),
                    "accuracy":    eval_m.get("accuracy"),
                    "roc_auc":     eval_m.get("roc_auc"),
                    "saved_at":    meta.get("saved_at"),
                    "is_active":   False,
                })
        return versions


# ── Thread-safe Singleton ─────────────────────────────────────────────────────
_tracker_instance: Optional[ModelVersionTracker] = None
_tracker_lock     = threading.Lock()


def get_version_tracker() -> ModelVersionTracker:
    global _tracker_instance
    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = ModelVersionTracker()
    return _tracker_instance