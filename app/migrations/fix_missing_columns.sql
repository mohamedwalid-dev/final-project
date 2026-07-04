-- ============================================================
-- Migration: fix_missing_columns.sql
-- Adds columns that exist in db.py but are missing in MySQL.
-- Run once: mysql -u root -p ai_erp < fix_missing_columns.sql
-- ============================================================

-- 1. events table — add processed_at column
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS processed_at DATETIME NULL DEFAULT NULL;

-- 2. execution_tracker table — add all expected columns
ALTER TABLE execution_tracker
    ADD COLUMN IF NOT EXISTS workflow        VARCHAR(100)  NOT NULL DEFAULT '' AFTER id,
    ADD COLUMN IF NOT EXISTS trigger_source  VARCHAR(100)  NOT NULL DEFAULT '' AFTER workflow,
    ADD COLUMN IF NOT EXISTS entity_id       INT           NOT NULL DEFAULT 0  AFTER trigger_source,
    ADD COLUMN IF NOT EXISTS status          VARCHAR(50)   NOT NULL DEFAULT 'running' AFTER entity_id,
    ADD COLUMN IF NOT EXISTS error_message   TEXT          NULL DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS started_at      DATETIME      NULL DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS finished_at     DATETIME      NULL DEFAULT NULL;

-- Verify
SELECT 'events columns:' AS msg;
SHOW COLUMNS FROM events;

SELECT 'execution_tracker columns:' AS msg;
SHOW COLUMNS FROM execution_tracker;
