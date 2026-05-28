-- 054_decouple_build_projects_from_categories.sql
--
-- Req #2723: build_projects is a top-level Build Visualizer entity and does
-- not need a categorization dimension. The schema previously declared
-- build_projects.category_fk NOT NULL FK -> categories(id) ON DELETE RESTRICT,
-- which forced seed_build_projects.py to insert a 'Build Projects' row in the
-- categories table just to host the 3 real build_projects rows. That row
-- then leaked into the Requirements UI as a ghost category that could not be
-- deleted (FK constraint -> 500).
--
-- Fix: drop the FK + column from build_projects, then delete the now-orphan
-- 'Build Projects' categories rows. The 3 real build_projects rows
-- ("Sample Project", "Default", "Sprint Cycle") are preserved untouched.
--
-- Verified on 2026-05-28:
--   darwin     cat id=1202 (creator 37df7531-..., project_fk=1)   — only Build Projects row
--   darwin_dev cat id=635  (creator 37df7531-..., project_fk=409) — only Build Projects row
--
-- The DELETE filters by name only — if a future user has reqs/features/
-- test_cases/test_plans pointing at a 'Build Projects' category the
-- ON DELETE RESTRICT on those FKs will abort the DELETE and the migration
-- fails closed. Today no such rows exist.

ALTER TABLE build_projects
    DROP FOREIGN KEY fk_build_projects_category;

ALTER TABLE build_projects
    DROP COLUMN category_fk;

DELETE FROM categories WHERE category_name = 'Build Projects';
