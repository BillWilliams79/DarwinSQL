-- 20260811033413_drop_feature_schema_features_feature_test_cases_requirements.sql
--
-- Req #3355 (Pipeline 2.0 eradication phase E6): drop the Feature schema now
-- that nothing needs it — Pipeline 2.0 seats a step under an epic directly
-- (epic_fk on the step), and the test-case catalog re-homed onto Requirement
-- via requirement_test_cases (req #3352, migration 20260809002149).
--
-- PROBLEM.  `features`, `feature_test_cases` and `requirements.feature_fk`
--           implement the retired requirement -> feature -> epic chain
--           (Epic > Feature > Story, req #3111). Nothing authors against it
--           any more (instruction #92 closed, #95 rewritten for containment,
--           req #3353) and its two consumers have been re-pointed: the
--           test-case junction now runs through requirement_test_cases
--           (verified 2026-08-11 by direct production query — all 28
--           feature_test_cases rows have a requirement_test_cases row
--           sharing the same test_case_fk, and darwin_dev the same for its
--           28 production-equivalent rows plus dogfood extras), and a
--           Pipeline 2.0 step's epic is read directly off the step
--           (epic_fk), never walked through Feature.
--
-- SHAPE.    Three drops, forced into this order by FK dependency:
--             1. feature_test_cases  (leaf — PK (feature_fk, test_case_fk),
--                FKs to features and test_cases, both ON DELETE CASCADE)
--             2. requirements.feature_fk (+ its FK fk_requirements_feature
--                and the column itself)
--             3. features (now referenced by nothing)
--           No data migration: feature_test_cases' only surviving obligation
--           (a requirement-junction equivalent for every row) was already
--           verified before this migration was written. requirements rows
--           simply lose the feature_fk column; no other column changes.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file. A
--           `USE` is a statement, not a declaration: it re-points the session
--           the moment it executes and overrides whatever database the caller
--           named — which on 2026-08-01 sent a dev-aimed apply to production.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--           If this migration may only be applied to ONE database, say so as a
--           constraint instead: `-- darwin:targets = darwin`.
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260811033413_drop_feature_schema_features_feature_test_cases_requirements.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260811033413_drop_feature_schema_features_feature_test_cases_requirements.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20260811033413` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- SEQUENCING. darwin-mcp's `TABLE_COLUMNS['requirements']` (services/common.py)
--           names `feature_fk` in its projected-read field list; Lambda-Rest
--           validates every `fields=` name against live `DESC requirements`
--           and 400s the WHOLE READ on an unknown column. The daemon MUST be
--           running code with `feature_fk` removed from that tuple BEFORE
--           this migration's production apply, or every `darwin://requirements/*`
--           read (including /swarm-start, /swarm-resume) 400s until it is
--           restarted. See memory/database.md § Projected tables.
--
-- Migration id 20260811033413 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.
--
-- darwin:destructive

DROP TABLE feature_test_cases;

ALTER TABLE requirements
    DROP FOREIGN KEY fk_requirements_feature,
    DROP COLUMN feature_fk;

DROP TABLE features;
