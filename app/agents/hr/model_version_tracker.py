"""
📦 Model Version Tracker — v1.0 Production
===========================================
File: app/agents/hr/model_version_tracker.py

🎯 Responsibilities:
    1. Save each trained model with a versioned filename (model_v1.pkl, model_v2.pkl, ...)
    2. Track all versions in DB table: model_versions
    3. Allow rollback to any previous version
    4. Expose version history for /model/versions endpoint

DB Schema (auto-created if not exists):
    CREATE TABLE IF NOT EXISTS model_versions (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        version      INT NOT NULL,
        filename     VARCHAR(255) NOT NULL,
        data_source  VARCHAR(100),
        accuracy     FLOAT,
        roc_auc      FLOAT,
        f1_score     FLOAT,
        monthly_cost FLOAT,
        trained_at   DATETIME NOT NULL,
        is_active    TINYINT(1) DEFAULT 0,
        notes        TEXT,
        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
    );
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE        = Path(__file__).resolve().parent.parent.parent
MODEL_DIR    = _BASE / "app" / "models" / "hr"
VERSIONS_DIR = MODEL_DIR / "versions"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

# File names
ACTIVE_MODEL_PATH   = MODEL_DIR / "leave_approval_model.pkl"
ACTIVE_SCALER_PATH  = MODEL_DIR / "scaler.pkl"
ACTIVE_ENCODER_PATH = MODEL_DIR / "encoders.pkl"
ACTIVE_META_PATH    = MODEL_DIR / "model_metadata.json"


# ════════════════════════════════════════════════════════════════════════════
# 📦  MODEL VERSION TRACKER
# ════════════════════════════════════════════════════════════════════════════

class ModelVersionTracker:
    """
    Tracks ML model versions with filesystem snapshots + DB records.

    Usage (from training pipeline):
        tracker = get_version_tracker()
        version = tracker.save_new_version(metadata)
        print(f"Saved as v{version}")

    Usage (rollback):
        tracker.rollback_to_version(version=2)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._ensure_db_table()

    # ── Public API ────────────────────────────────────────────────────────────

    def save_new_version(self, metadata: dict) -> int:
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

            # Save metadata snapshot alongside artifacts
            snapshot_meta = {
                "version":    next_version,
                "saved_at":   datetime.utcnow().isoformat() + "Z",
                "files":      copied,
                **metadata,
            }
            meta_snapshot = version_dir / "version_metadata.json"
            with open(meta_snapshot, "w", encoding="utf-8") as f:
                json.dump(snapshot_meta, f, indent=2, ensure_ascii=False)

            # Record in DB
            self._record_in_db(next_version, metadata, snapshot_meta)

            logger.info(
                "📦 [ModelVersionTracker] Saved model v%d → %s | "
                "accuracy=%s | AUC=%s",
                next_version,
                version_dir,
                metadata.get("evaluation", {}).get("accuracy", "?"),
                metadata.get("evaluation", {}).get("roc_auc", "?"),
            )

            return next_version

    def rollback_to_version(self, version: int) -> bool:
        """
        Restore a previously saved model version as the active model.
        Overwrites the current active model files.

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
                # Map versioned filename → active filename
                dst_map = {
                    "leave_approval_model.pkl": ACTIVE_MODEL_PATH,
                    "scaler.pkl":               ACTIVE_SCALER_PATH,
                    "encoders.pkl":             ACTIVE_ENCODER_PATH,
                }
                dst = dst_map.get(src.name)
                if dst:
                    shutil.copy2(src, dst)
                    restored.append(src.name)

            # Restore metadata
            src_meta = version_dir / "model_metadata.json"
            if src_meta.exists():
                shutil.copy2(src_meta, ACTIVE_META_PATH)
                restored.append("model_metadata.json")

            if not restored:
                logger.error("❌ [ModelVersionTracker] No files restored for v%d.", version)
                return False

            # Update DB active flag
            self._set_active_version(version)

            logger.info(
                "✅ [ModelVersionTracker] Rolled back to v%d | files: %s",
                version, restored,
            )
            return True

    def list_versions(self, limit: int = 20) -> list[dict]:
        """Return version history (newest first) from DB or filesystem fallback."""
        try:
            from core.db import get_db
            with get_db() as (_, cur):
                cur.execute(
                    """
                    SELECT version, filename, data_source, accuracy, roc_auc,
                           f1_score, monthly_cost, trained_at, is_active, notes
                    FROM model_versions
                    ORDER BY version DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "version":      r["version"],
                        "filename":     r["filename"],
                        "data_source":  r["data_source"],
                        "accuracy":     r["accuracy"],
                        "roc_auc":      r["roc_auc"],
                        "f1_score":     r["f1_score"],
                        "monthly_cost": r["monthly_cost"],
                        "trained_at":   r["trained_at"].isoformat() if r["trained_at"] else None,
                        "is_active":    bool(r["is_active"]),
                        "notes":        r["notes"],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning("⚠️ [ModelVersionTracker] DB list failed: %s — using filesystem", e)
            return self._list_from_filesystem()

    def get_active_version(self) -> Optional[dict]:
        """Return info about the currently active model version."""
        try:
            from core.db import get_db
            with get_db() as (_, cur):
                cur.execute(
                    "SELECT * FROM model_versions WHERE is_active = 1 ORDER BY version DESC LIMIT 1"
                )
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception:
            return None

    def get_version_info(self, version: int) -> Optional[dict]:
        """Return metadata for a specific version."""
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

    def _record_in_db(self, version: int, metadata: dict, snapshot_meta: dict) -> None:
        """Insert a new version record into model_versions table."""
        try:
            from core.db import get_db
            eval_m = metadata.get("evaluation", {})
            cost_m = metadata.get("business_costs", {})
            with get_db() as (conn, cur):
                # Deactivate previous versions
                cur.execute("UPDATE model_versions SET is_active = 0")
                # Insert new version as active
                cur.execute(
                    """
                    INSERT INTO model_versions
                        (version, filename, data_source, accuracy, roc_auc,
                         f1_score, monthly_cost, trained_at, is_active, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
                    ON DUPLICATE KEY UPDATE
                        accuracy=VALUES(accuracy), roc_auc=VALUES(roc_auc),
                        is_active=1, trained_at=VALUES(trained_at)
                    """,
                    (
                        version,
                        f"leave_approval_model_v{version}.pkl",
                        metadata.get("data_source", "unknown"),
                        eval_m.get("accuracy"),
                        eval_m.get("roc_auc"),
                        eval_m.get("f1_score"),
                        cost_m.get("monthly_cost_egp"),
                        datetime.utcnow(),
                        json.dumps({
                            "n_samples":   metadata.get("n_training_samples"),
                            "thresholds":  metadata.get("thresholds"),
                            "saved_files": snapshot_meta.get("files", []),
                        }),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.warning(
                "⚠️ [ModelVersionTracker] DB record failed (non-critical): %s. "
                "Version saved to filesystem only.",
                e,
            )

    def _set_active_version(self, version: int) -> None:
        """Mark a specific version as active in DB."""
        try:
            from core.db import get_db
            with get_db() as (conn, cur):
                cur.execute("UPDATE model_versions SET is_active = 0")
                cur.execute(
                    "UPDATE model_versions SET is_active = 1 WHERE version = %s",
                    (version,),
                )
                conn.commit()
        except Exception as e:
            logger.warning("⚠️ [ModelVersionTracker] DB active flag update failed: %s", e)

    def _ensure_db_table(self) -> None:
        """Create model_versions table if it doesn't exist."""
        try:
            from core.db import get_db
            with get_db() as (conn, cur):
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS model_versions (
                        id           INT AUTO_INCREMENT PRIMARY KEY,
                        version      INT NOT NULL UNIQUE,
                        filename     VARCHAR(255) NOT NULL,
                        data_source  VARCHAR(100),
                        accuracy     FLOAT,
                        roc_auc      FLOAT,
                        f1_score     FLOAT,
                        monthly_cost FLOAT,
                        trained_at   DATETIME NOT NULL,
                        is_active    TINYINT(1) DEFAULT 0,
                        notes        TEXT,
                        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_is_active (is_active),
                        INDEX idx_version   (version)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
                conn.commit()
        except Exception as e:
            logger.warning(
                "⚠️ [ModelVersionTracker] Could not create model_versions table: %s. "
                "Will use filesystem only.",
                e,
            )

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
                    "is_active":   False,  # can't determine without DB
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