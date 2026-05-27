-- 051_add_external_id_to_build_data.sql
--
-- Req #2648: SQL-backed Build Visualizer storage.
--
-- Adds `external_id` to branches and builds so the iframe's slug-style ids
-- ("main", "release-1", "m1", "r1c", "sr3", …) round-trip through SQL. The
-- iframe model uses these slugs as primary keys; the SqlBackedStorageAdapter
-- maintains a slug → SQL id map at load time and uses it to issue minimal
-- POST/PUT/DELETE on save.
--
-- Scoping rules:
--   * external_id is unique within (project_fk) for branches (the trunk is
--     'main' for every project; release-N etc. are unique within a project).
--   * external_id is unique within (branch_fk) for builds.
-- Both columns are NULLable for backward compatibility with rows seeded
-- before req #2648 (the seed_build_projects.py change in this same req
-- populates them going forward).

ALTER TABLE branches
    ADD COLUMN external_id VARCHAR(64) NULL,
    ADD INDEX idx_branches_project_external (project_fk, external_id);

ALTER TABLE builds
    ADD COLUMN external_id VARCHAR(64) NULL,
    ADD INDEX idx_builds_branch_external (branch_fk, external_id);
