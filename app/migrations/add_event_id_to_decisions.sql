-- ============================================================
-- Migration: add_event_id_to_decisions.sql
-- Adds event_id FK column to decisions table.
-- Run once: mysql -u root -p ai_erp < add_event_id_to_decisions.sql
--
-- ✅ Fix: decisions.event_id → references events(id)
--    - NULL allowed (for legacy calls without events)
--    - FK ensures data integrity when event_id IS set
-- ============================================================

-- 1. Add event_id column if missing
ALTER TABLE decisions
    ADD COLUMN IF NOT EXISTS event_id INT NULL DEFAULT NULL AFTER id;

-- 2. Add Foreign Key (only if not already present)
-- Check if FK exists first to avoid duplicate constraint errors
SET @fk_exists = (
    SELECT COUNT(*)
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'decisions'
      AND CONSTRAINT_NAME = 'fk_decisions_event_id'
);

SET @sql = IF(@fk_exists = 0,
    'ALTER TABLE decisions ADD CONSTRAINT fk_decisions_event_id FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE SET NULL',
    'SELECT "FK already exists" AS msg'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verify
SELECT 'decisions columns after migration:' AS msg;
SHOW COLUMNS FROM decisions;
