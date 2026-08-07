-- Migration 005: Add sort_order column to areas
-- Supports sorting areas in the UI and retaining settings across devices/logins
--
-- The `USE darwin;` that stood here was removed by req #3196 — a migration file
-- must not choose its own database. Name the target on the connection:
--   python3 DarwinSQL/scripts/load_sql.py <this file> darwin_dev

ALTER TABLE areas
ADD COLUMN sort_order SMALLINT;
