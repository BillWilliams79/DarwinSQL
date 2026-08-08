-- Migration 003: Add closed column to domains
-- Supports ability to close (hide) domains from task plan view
--
-- The `USE darwin;` that stood here was removed by req #3196 — a migration file
-- must not choose its own database. Name the target on the connection:
--   python3 DarwinSQL/scripts/load_sql.py <this file> darwin_dev

ALTER TABLE domains
ADD COLUMN closed TINYINT NOT NULL DEFAULT 0;
