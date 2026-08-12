-- 20260812184333_rename_pipeline2_to_plain_names_now_that_1_0_is_gone.sql
--
-- Req #3356, second half: now that the first-generation pipeline layer is
-- archived and dropped (migration 20260812175325), rename the second
-- generation's tables/constraints/indexes to drop their `2`/`p2` era marker.
-- User's own ruling: "I do not want any UI element or skills to refer to
-- pipeline2 ... eradicate then rename is the game."
--
-- PROBLEM.  `pipeline2_*` was a transitional era marker, never a permanent
--           name. With only one generation left, keeping the marker invites
--           exactly the confusion it was meant to prevent — a future reader
--           asking "where is generation 1, and why does everything say 2".
--
-- SHAPE.    RENAME TABLE for the five tables (a metadata-only operation —
--           InnoDB FKs from swarm_sessions/orchestration_claims follow the
--           rename automatically, no re-pointing needed). Then DROP+ADD each
--           `fk_p2_*` constraint under its plain name (MySQL has no
--           `RENAME CONSTRAINT` for foreign keys) and `RENAME INDEX` for the
--           plain (non-FK-backing) indexes. orchestration_claims' 2.0 scope
--           pair (pipeline2_fk/epic2_fk/epic2_key) becomes the only pair
--           (pipeline_fk/epic_fk/epic_key) — the generated column is
--           dropped and re-added rather than renamed in place, because MySQL
--           refuses to RENAME COLUMN a column a generated column's
--           expression still references by its old name.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260812184333_rename_pipeline2_to_plain_names_now_that_1_0_is_gone.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260812184333_rename_pipeline2_to_plain_names_now_that_1_0_is_gone.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20260812184333` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20260812184333 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

SET FOREIGN_KEY_CHECKS = 0;

-- --- Table renames — one atomic statement, FKs follow automatically --------
RENAME TABLE
    pipeline2_pipelines           TO pipelines,
    pipeline2_epics                TO epics,
    pipeline2_steps                TO pipeline_steps,
    pipeline2_step_requirements    TO pipeline_step_requirements,
    pipeline2_step_deps            TO pipeline_step_deps;

-- --- pipelines: rename its two FK constraints --------------------------------
ALTER TABLE pipelines
    DROP FOREIGN KEY fk_p2_pipelines_machine,
    ADD CONSTRAINT fk_pipelines_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    DROP FOREIGN KEY fk_p2_pipelines_creator,
    ADD CONSTRAINT fk_pipelines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE;

-- --- epics: rename its three FK constraints + its index ---------------------
ALTER TABLE epics
    DROP FOREIGN KEY fk_p2_epics_pipeline,
    ADD CONSTRAINT fk_epics_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    DROP FOREIGN KEY fk_p2_epics_category,
    ADD CONSTRAINT fk_epics_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    DROP FOREIGN KEY fk_p2_epics_creator,
    ADD CONSTRAINT fk_epics_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    RENAME INDEX ix_p2_epics_pipeline_fk TO ix_epics_pipeline_fk;

-- --- pipeline_steps: rename its two FK constraints + its index -------------
ALTER TABLE pipeline_steps
    DROP FOREIGN KEY fk_p2_steps_epic,
    ADD CONSTRAINT fk_pipeline_steps_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    DROP FOREIGN KEY fk_p2_steps_creator,
    ADD CONSTRAINT fk_pipeline_steps_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    RENAME INDEX ix_p2_steps_epic_fk TO ix_pipeline_steps_epic_fk;

-- --- pipeline_step_requirements: rename its two FK constraints -------------
ALTER TABLE pipeline_step_requirements
    DROP FOREIGN KEY fk_p2_psr_step,
    ADD CONSTRAINT fk_psr_step
        FOREIGN KEY (step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    DROP FOREIGN KEY fk_p2_psr_requirement,
    ADD CONSTRAINT fk_psr_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- --- pipeline_step_deps: rename its unique key, two FKs and its index ------
ALTER TABLE pipeline_step_deps
    RENAME INDEX uq_p2_step_deps TO uq_pipeline_step_deps,
    DROP FOREIGN KEY fk_p2_psd_step,
    ADD CONSTRAINT fk_psd_step
        FOREIGN KEY (step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    DROP FOREIGN KEY fk_p2_psd_dep_step,
    ADD CONSTRAINT fk_psd_dep_step
        FOREIGN KEY (dep_step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    RENAME INDEX ix_p2_psd_dep_step_fk TO ix_psd_dep_step_fk;

-- --- orchestration_claims: the 2.0 scope pair becomes the only pair --------
-- epic2_key is a generated column referencing epic2_fk by name — it must be
-- dropped before epic2_fk can be renamed, and re-added afterward under the
-- new column's name.
ALTER TABLE orchestration_claims
    DROP INDEX uq_orchestration_claims_scope2,
    DROP INDEX ix_orchestration_claims_epic2_fk,
    DROP FOREIGN KEY fk_oc_pipeline2,
    DROP FOREIGN KEY fk_oc_epic2,
    DROP COLUMN epic2_key,
    RENAME COLUMN pipeline2_fk TO pipeline_fk,
    RENAME COLUMN epic2_fk TO epic_fk,
    ADD COLUMN epic_key INT GENERATED ALWAYS AS (COALESCE(epic_fk, 0)) VIRTUAL,
    ADD UNIQUE KEY uq_orchestration_claims_scope (pipeline_fk, epic_key),
    ADD KEY ix_orchestration_claims_epic_fk (epic_fk),
    ADD CONSTRAINT fk_oc_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    ADD CONSTRAINT fk_oc_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE;

-- --- swarm_sessions: the 2.0 attribution pair becomes the only pair --------
ALTER TABLE swarm_sessions
    DROP FOREIGN KEY fk_swarm_sessions_pipeline2,
    DROP FOREIGN KEY fk_swarm_sessions_epic2,
    RENAME COLUMN pipeline2_fk TO pipeline_fk,
    RENAME COLUMN epic2_fk TO epic_fk,
    ADD CONSTRAINT fk_swarm_sessions_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    ADD CONSTRAINT fk_swarm_sessions_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE SET NULL;

SET FOREIGN_KEY_CHECKS = 1;

