-- 20260812175325_drop_1_0_pipeline_layer_pipelines_pipeline_steps_pipeline_st.sql
--
-- Req #3356: drop the first-generation pipeline layer — pipelines,
-- pipeline_steps, pipeline_step_requirements, pipeline_step_deps, epics — and
-- the 1.0 attribution columns on swarm_sessions and orchestration_claims. 2.0
-- (pipeline2_pipelines / pipeline2_epics / pipeline2_steps /
-- pipeline2_step_requirements / pipeline2_step_deps) has run beside 1.0 since
-- req #3328 and has been observed doing the same job on the same work
-- (memory/pipeline-2-performance-report.md, req #3383). No live 1.0
-- orchestration exists at the time of this migration (verified:
-- darwin://orchestration-claims held zero 1.0-scope rows).
--
-- PROBLEM.  Every table this drops has a live 2.0 replacement already serving
--           production. Keeping both means every future schema change to the
--           plan layer is written twice, and every reader has to know which
--           era's tables a given code path means.
--
-- SHAPE.    Five tables dropped whole. Two columns dropped from
--           swarm_sessions (pipeline_fk, epic_fk — 1.0 orchestration
--           attribution, req #3186; the 2.0 pair pipeline2_fk/epic2_fk is
--           untouched). orchestration_claims loses its 1.0 scope columns
--           (pipeline_fk, epic_fk, and the generated epic_key that derives
--           from epic_fk) and their unique key + index; its 2.0 pair
--           (pipeline2_fk, epic2_fk, epic2_key) is untouched. Drop order is
--           forced by FKs: pipeline_step_deps first (its dep_step_fk is
--           ON DELETE RESTRICT against pipeline_steps, so it must go before
--           pipeline_steps can), then pipeline_step_requirements, then
--           pipeline_steps, then pipelines, then epics (referenced only by
--           the two attribution columns already dropped above).
--
-- ARCHIVE.  Every row of all five tables, plus the 1.0 attribution column
--           values, is archived to DarwinSQL/recovered/*.jsonl BEFORE this
--           migration runs (stage-2 gate ruling, req #3336: "the data
--           archived and no one will ever care again") — see
--           scripts/db/archive-pipeline-1-0-before-drop.sh, run and verified
--           against production before this file is applied.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file. A
--           `USE` is a statement, not a declaration: it re-points the session
--           the moment it executes and overrides whatever database the caller
--           named — which on 2026-08-01 sent a dev-aimed apply to production.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260812175325_drop_1_0_pipeline_layer_pipelines_pipeline_steps_pipeline_st.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260812175325_drop_1_0_pipeline_layer_pipelines_pipeline_steps_pipeline_st.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20260812175325` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20260812175325 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

SET FOREIGN_KEY_CHECKS = 0;

-- --- swarm_sessions: drop the 1.0 attribution pair -------------------------
ALTER TABLE swarm_sessions
    DROP FOREIGN KEY fk_swarm_sessions_pipeline,
    DROP FOREIGN KEY fk_swarm_sessions_epic,
    DROP COLUMN pipeline_fk,
    DROP COLUMN epic_fk;

-- --- orchestration_claims: drop the 1.0 scope pair --------------------------
-- Order matters: the unique key and index must go before the FKs they sit on,
-- and epic_key (a generated column deriving from epic_fk) must go before
-- epic_fk itself.
ALTER TABLE orchestration_claims
    DROP INDEX ix_orchestration_claims_epic_fk,
    DROP INDEX uq_orchestration_claims_scope,
    DROP FOREIGN KEY fk_oc_pipeline,
    DROP FOREIGN KEY fk_oc_epic,
    DROP COLUMN epic_key,
    DROP COLUMN pipeline_fk,
    DROP COLUMN epic_fk;

-- --- The four 1.0 plan tables, leaf to root ---------------------------------
DROP TABLE pipeline_step_deps;
DROP TABLE pipeline_step_requirements;
DROP TABLE pipeline_steps;
DROP TABLE pipelines;

-- --- The 1.0 epics table -----------------------------------------------------
-- Its only referencers (swarm_sessions.epic_fk, orchestration_claims.epic_fk)
-- were dropped above.
DROP TABLE epics;

SET FOREIGN_KEY_CHECKS = 1;

