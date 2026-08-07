-- Migration 006: Expand task description field
-- User request to allow longer task descriptions (256 -> 1024)
--
-- The `USE darwin;` that stood here was removed by req #3196 — a migration file
-- must not choose its own database. Name the target on the connection:
--   python3 DarwinSQL/scripts/load_sql.py <this file> darwin_dev

ALTER TABLE tasks
MODIFY COLUMN description VARCHAR(1024) NOT NULL;
