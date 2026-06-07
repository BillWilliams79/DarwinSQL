-- 057_drop_build_visualizer_from_production.sql
--
-- Req #2760: The Build Visualizer is a dev/design tool, not a production
-- end-user feature. Its data + schema must live ONLY in `darwin_dev`, never in
-- production `darwin`. This migration removes the 5 build-visualizer tables
-- (data + schema) from production.
--
-- ============================================================================
-- PRODUCTION-ONLY MIGRATION — DO NOT APPLY TO darwin_dev.
-- ============================================================================
-- Unlike every other migration in this directory, 057 is applied to production
-- `darwin` ONLY. `darwin_dev` intentionally RETAINS the full build-visualizer
-- schema + seed data, because the Build Visualizer remains a fully-functional
-- dev-only tool there (MCP + frontend are repointed to `darwin_dev` in the same
-- req #2760 change set: darwin-mcp/db.py get_buildviz_connection(), and the
-- frontend `darwinBuildVizUri` pin in Darwin/src/Context/AppContext.jsx).
--
-- Consequently the schema-of-record files are deliberately NOT changed by this
-- migration: `DarwinSQL/schema.sql` and `DarwinSQL/scripts/recreate_darwin_dev.sql`
-- remain the canonical / dev-superset (they already carry `builds.major`/`minor`
-- from migration 055, which production also lacks — see database.md § Schema
-- Drift Incident). The DarwinSQL test suite runs against `darwin_dev`, which keeps
-- all tables, so no test changes accompany this migration.
--
-- After this runs, production `darwin` is "behind" the schema-of-record by these
-- 5 tables, the same documented way it is behind on migration 055.
--
-- ----------------------------------------------------------------------------
-- Removal scope (production row counts verified 2026-06-01):
--   customer_releases   (7 rows)
--   builds              (369 rows)
--   branches            (90 rows)
--   build_projects      (4 rows: Sample Project, Default, Sprint Cycle, SwitchTec)
--   customers           (4 rows)
--
-- `customers` is dropped WITH the build-viz set: it is a build-visualizer-only
-- entity (referenced only by customer_releases, and surfaced only by the
-- dev-only Customers / Customer Releases pages). No core production feature
-- references it.
--
-- FK dependency chain (customer_releases -> {customers, builds};
-- builds -> branches; branches -> build_projects; build_projects <-> branches
-- circular via trunk_branch_fk). FK checks are disabled around the DROP block so
-- the circular references and RESTRICT guard on customer_releases.customer_fk do
-- not block the teardown — identical to the FK-checks-off pattern schema.sql and
-- recreate_darwin_dev.sql use to CREATE these same tables.
--
-- Rollback: restore from the mandatory pre-migration RDS snapshot
-- (darwin-pre-migration-057-<timestamp>). darwin_dev still holds an equivalent,
-- freshly-reseeded build-visualizer dataset.
-- ----------------------------------------------------------------------------

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS customer_releases;
DROP TABLE IF EXISTS builds;
DROP TABLE IF EXISTS branches;
DROP TABLE IF EXISTS build_projects;
DROP TABLE IF EXISTS customers;

SET FOREIGN_KEY_CHECKS = 1;
