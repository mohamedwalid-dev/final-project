"""
📦 Model Version Tracker — v2.0 Production (MongoDB)
=====================================================
File: app/agents/hr/model_version_tracker.py

🎯 Responsibilities:
    1. Save each trained model with a versioned filename (model_v1.pkl, model_v2.pkl, ...)
    2. Track all versions in MongoDB collection: model_versions
    3. Allow rollback to any previous version
    4. Expose version history for /model/versions endpoint

MongoDB collection schema (auto-created via insert):
    {
        version:      int,
        filename:     str,
        data_source:  str,
        accuracy:     float,
        roc_auc:      float,
        f1_score:     float,
        monthly_cost: float,
        trained_at:   datetime,
        is_active:    bool,
        notes:        str | dict,
        created_at:   datetime,
    }
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ════════════════════════════════════════════════════════════════════════════
# 📦  MODEL VERSION TRACKER
# ════════════════════════════════════════════════════════════════════════════

class ModelVersionTracker:
    """
    Tracks ML model versions with filesystem snapshots + MongoDB records.

    Usage (from training pipeline):
        tracker = get_version_tracker()
        version = await tracker.save_new_version(metadata)

    Usage (rollback):
        await tracker.rollback_to_version(version=2)
    """

    def __init__(self):
        self._lock = threading.Lock()

    def _get_collection(self):
        """Return Motor collection for model_versions."""
        from core.mongo_connect import get_hr_db
        db = get_hr_db()
        return db.db["model_versions"]

    async def _ensure_indexes(self) -> None:
        """Create indexes on model_versions collection (idempotent)."""
        try:
            col = self._get_collection()
            await col.create_index("version", unique=True)
            await col.create_index("is_active")
            await col.create_index("trained_at")
        except Exception as e:
            logger.warning("⚠️ [ModelVersionTracker] Index creation failed: %s", e)

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

            await self._record_in_db(next_version, metadata, snapshot_meta)

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

            await self._set_active_version(version)

            logger.info(
                "✅ [ModelVersionTracker] Rolled back to v%d | files: %s",
                version, restored,
            )
            return True

    async def list_versions(self, limit: int = 20) -> list[dict]:
        """Return version history (newest first) from MongoDB or filesystem fallback."""
        try:
            col    = self._get_collection()
            cursor = col.find({}).sort("version", -1).limit(limit)
            rows   = await cursor.to_list(None)
            result = []
            for r in rows:
                result.append({
                    "version":      r.get("version"),
                    "filename":     r.get("filename"),
                    "data_source":  r.get("data_source"),
                    "accuracy":     r.get("accuracy"),
                    "roc_auc":      r.get("roc_auc"),
                    "f1_score":     r.get("f1_score"),
                    "monthly_cost": r.get("monthly_cost"),
                    "trained_at":   r["trained_at"].isoformat() if isinstance(r.get("trained_at"), datetime) else r.get("trained_at"),
                    "is_active":    bool(r.get("is_active", False)),
                    "notes":        r.get("notes"),
                })
            return result
        except Exception as e:
            logger.warning("⚠️ [ModelVersionTracker] DB list failed: %s — using filesystem", e)
            return self._list_from_filesystem()

    async def get_active_version(self) -> Optional[dict]:
        """Return info about the currently active model version."""
        try:
            col = self._get_collection()
            doc = await col.find_one({"is_active": True}, sort=[("version", -1)])
            if not doc:
                return None
            doc.pop("_id", None)
            if isinstance(doc.get("trained_at"), datetime):
                doc["trained_at"] = doc["trained_at"].isoformat()
            return doc
        except Exception as e:
            logger.warning("⚠️ [ModelVersionTracker] get_active_version failed: %s", e)
            return None

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

    async def _record_in_db(self, version: int, metadata: dict, snapshot_meta: dict) -> None:
        """Insert (or update) a version record in MongoDB model_versions collection."""
        try:
            col    = self._get_collection()
            eval_m = metadata.get("evaluation", {})
            cost_m = metadata.get("business_costs", {})

            # Deactivate all previous versions
            await col.update_many({}, {"$set": {"is_active": False}})

            doc = {
                "version":      version,
                "filename":     f"leave_approval_model_v{version}.pkl",
                "data_source":  metadata.get("data_source", "unknown"),
                "accuracy":     eval_m.get("accuracy"),
                "roc_auc":      eval_m.get("roc_auc"),
                "f1_score":     eval_m.get("f1_score"),
                "monthly_cost": cost_m.get("monthly_cost_egp"),
                "trained_at":   _utcnow(),
                "is_active":    True,
                "notes":        {
                    "n_samples":   metadata.get("n_training_samples"),
                    "thresholds":  metadata.get("thresholds"),
                    "saved_files": snapshot_meta.get("files", []),
                },
                "created_at":   _utcnow(),
            }

            await col.update_one(
                {"version": version},
                {"$set": doc},
                upsert=True,
            )
        except Exception as e:
            logger.warning(
                "⚠️ [ModelVersionTracker] DB record failed (non-critical): %s. "
                "Version saved to filesystem only.",
                e,
            )

    async def _set_active_version(self, version: int) -> None:
        """Mark a specific version as active in MongoDB."""
        try:
            col = self._get_collection()
            await col.update_many({}, {"$set": {"is_active": False}})
            await col.update_one(
                {"version": version},
                {"$set": {"is_active": True}},
            )
        except Exception as e:
            logger.warning("⚠️ [ModelVersionTracker] DB active flag update failed: %s", e)

    def _list_from_filesystem(self) -> list[dict]:
        """Fallback: list versions from filesystem when DB is unavailable."""
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