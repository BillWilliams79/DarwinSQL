-- Migration 009: Add scheduled column to priorities table
-- Marks priorities for batch swarm-start launch via UI toggle.

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'priorities' AND COLUMN_NAME = 'scheduled');

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE priorities ADD COLUMN scheduled TINYINT NOT NULL DEFAULT 0',
    'SELECT 1');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
