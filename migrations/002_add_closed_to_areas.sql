-- Migration 002: Add closed column to areas
-- Supports ability to close (hide) areas from task plan view
--
-- The `USE darwin;` that stood here was removed by req #3196 — a migration file
-- must not choose its own database. Name the target on the connection:
--   python3 DarwinSQL/scripts/load_sql.py <this file> darwin_dev

ALTER TABLE areas
ADD COLUMN closed TINYINT NOT NULL DEFAULT 0;
